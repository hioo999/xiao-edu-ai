from apps.api.app.media.gateway import MediaGenerationResult
from apps.api.app.media.jobs import JobState, MediaJobLedger
from apps.api.app.media.worker import MediaGenerationWorker
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault
from apps.api.app.models.calls import ModelCallLog
from apps.api.app.projects.catalog import CreativeAssetCatalog


class FakeMediaGateway:
    def submit(self, provider: ModelProvider, job):
        return MediaGenerationResult(state="succeeded", preview_url="https://cdn.example.test/cat.png", lyrics="星星点亮夜空\n我们一起出发", duration_seconds=42)


class FailingMediaGateway:
    def submit(self, provider: ModelProvider, job):
        raise ValueError("provider temporarily unavailable")


class EmptyMediaGateway:
    def submit(self, provider: ModelProvider, job):
        return MediaGenerationResult(state="succeeded")


class NoLyricsMediaGateway:
    def submit(self, provider: ModelProvider, job):
        return MediaGenerationResult(state="succeeded", preview_url="https://cdn.example.test/song.mp3")


class RecordingQueue:
    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.dead_letters: list[tuple[str, str]] = []

    def enqueue(self, job_id: str) -> None:
        self.enqueued.append(job_id)

    def dequeue(self, timeout_seconds: int = 1) -> str | None:
        return None

    def dead_letter(self, job_id: str, error: str) -> None:
        self.dead_letters.append((job_id, error))


def test_worker_generates_image_and_saves_pending_work() -> None:
    registry = ProviderRegistry(SecretVault(b"azM6hQeWYBhU6oFFUAhzwSctltmU3TdoQ-lxYj-2OCQ="))
    registry.register(ModelProvider("doubao-image", "org-001", ModelCapability.IMAGE, "domestic", 1, "secret", provider_kind="doubao", model_id="doubao-seedream", base_url="https://ark.cn-beijing.volces.com/api/v3"))
    ledger = MediaJobLedger()
    job = ledger.create("image", "student-001", organization_id="org-001", prompt="太空小猫")
    assets = CreativeAssetCatalog()

    calls = ModelCallLog()
    processed = MediaGenerationWorker(ledger, registry, assets, FakeMediaGateway(), call_log=calls).process_once()

    assert processed == 1
    assert ledger.get(job.job_id).state is JobState.SUCCEEDED
    work = assets.list_for_owner("student-001", "org-001")[0]
    assert work.preview_url == "https://cdn.example.test/cat.png"
    assert work.review_state == "pending"
    assert work.lyrics == "星星点亮夜空\n我们一起出发"
    assert work.duration_seconds == 42
    assert calls.recent("org-001")[0].capability == "image"
    assert calls.recent("org-001")[0].outcome == "succeeded"


def test_worker_requeues_transient_provider_failure() -> None:
    registry = ProviderRegistry(SecretVault(b"azM6hQeWYBhU6oFFUAhzwSctltmU3TdoQ-lxYj-2OCQ="))
    registry.register(ModelProvider("doubao-image", "org-001", ModelCapability.IMAGE, "domestic", 1, "secret"))
    ledger = MediaJobLedger()
    job = ledger.create("image", "student-001", organization_id="org-001", prompt="太空小猫")
    queue = RecordingQueue()

    MediaGenerationWorker(ledger, registry, CreativeAssetCatalog(), FailingMediaGateway(), queue=queue).process_once()

    assert ledger.get(job.job_id).state is JobState.QUEUED
    assert queue.enqueued == [job.job_id]
    assert queue.dead_letters == []


def test_worker_does_not_mark_empty_media_as_succeeded() -> None:
    registry = ProviderRegistry(SecretVault(b"azM6hQeWYBhU6oFFUAhzwSctltmU3TdoQ-lxYj-2OCQ="))
    registry.register(ModelProvider("image-provider", "org-001", ModelCapability.IMAGE, "domestic", 1, "secret"))
    ledger = MediaJobLedger()
    job = ledger.create("image", "student-001", organization_id="org-001", prompt="太空小猫")
    calls = ModelCallLog()

    MediaGenerationWorker(ledger, registry, CreativeAssetCatalog(), EmptyMediaGateway(), call_log=calls).process_once()

    assert ledger.get(job.job_id).state is JobState.QUEUED
    assert calls.recent("org-001")[0].outcome == "failed"


def test_worker_preserves_student_lyrics_when_provider_returns_only_audio() -> None:
    registry = ProviderRegistry(SecretVault(b"azM6hQeWYBhU6oFFUAhzwSctltmU3TdoQ-lxYj-2OCQ="))
    registry.register(ModelProvider("music-provider", "org-001", ModelCapability.MUSIC, "domestic", 1, "secret"))
    ledger = MediaJobLedger()
    job = ledger.create("music", "student-001", organization_id="org-001", prompt="给星星谱曲", lyrics="星星亮晶晶")
    assets = CreativeAssetCatalog()

    MediaGenerationWorker(ledger, registry, assets, NoLyricsMediaGateway()).process_once()

    assert ledger.get(job.job_id).lyrics == "星星亮晶晶"
    assert assets.list_for_owner("student-001", "org-001")[0].lyrics == "星星亮晶晶"


def test_worker_respects_max_concurrency(monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_WORKER_MAX_CONCURRENCY", "1")
    registry = ProviderRegistry(SecretVault(b"azM6hQeWYBhU6oFFUAhzwSctltmU3TdoQ-lxYj-2OCQ="))
    registry.register(ModelProvider("doubao-image", "org-001", ModelCapability.IMAGE, "domestic", 1, "secret"))
    ledger = MediaJobLedger()
    first = ledger.create("image", "student-001", organization_id="org-001")
    second = ledger.create("image", "student-001", organization_id="org-001")

    processed = MediaGenerationWorker(ledger, registry, CreativeAssetCatalog(), FakeMediaGateway()).process_once()

    assert processed == 1
    assert ledger.get(first.job_id).state is JobState.SUCCEEDED
    assert ledger.get(second.job_id).state is JobState.QUEUED
