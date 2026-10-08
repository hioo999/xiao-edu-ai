import pytest

from apps.api.app.media.jobs import MediaJobLedger
from apps.api.app.media.queue import LedgerMediaJobQueue, build_media_job_queue


pytestmark = pytest.mark.unit


def test_ledger_media_queue_delegates_dead_letter_operations(tmp_path) -> None:
    ledger = MediaJobLedger(tmp_path / "media-jobs.sqlite")
    queue = LedgerMediaJobQueue(ledger)
    job = ledger.create("image", "student-001")
    ledger.start(job.job_id)
    ledger.fail(job.job_id, "provider timeout")

    queue.dead_letter(job.job_id, "provider timeout")
    assert queue.list_dead_letters() == [{"jobId": job.job_id, "error": "provider timeout"}]
    assert queue.retry_dead_letter(job.job_id) is True
    assert queue.list_dead_letters() == []


def test_ledger_media_queue_reports_worker_status_after_heartbeat(tmp_path) -> None:
    ledger = MediaJobLedger(tmp_path / "media-jobs.sqlite")
    queue = LedgerMediaJobQueue(ledger)

    queue.heartbeat()
    status = queue.worker_status()

    assert status["workerReady"] is True
    assert status["queueDepth"] == 0
    assert status["deadLetterDepth"] == 0
    assert status["lastHeartbeat"] is not None


def test_build_media_job_queue_uses_ledger_fallback_without_redis(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    ledger = MediaJobLedger(tmp_path / "media-jobs.sqlite")
    queue = build_media_job_queue(ledger)
    assert isinstance(queue, LedgerMediaJobQueue)
