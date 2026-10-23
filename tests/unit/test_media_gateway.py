import httpx
import json
import pytest
from cryptography.fernet import Fernet

from apps.api.app.media.gateway import MediaProviderGateway
from apps.api.app.media.jobs import MediaJobLedger
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


pytestmark = pytest.mark.unit


def make_provider(kind: str, capability: ModelCapability) -> tuple[ProviderRegistry, ModelProvider]:
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    provider = ModelProvider(
        "audio-provider",
        "org-001",
        capability,
        "domestic",
        1,
        "audio-secret",
        provider_kind=kind,
        model_id="audio-model",
        base_url="https://audio.example.test/v1",
    )
    registry.register(provider)
    return registry, provider


@pytest.mark.parametrize(
    ("kind", "capability", "job_kind", "path", "response"),
    [
        ("custom", ModelCapability.TEXT_TO_SPEECH, "voice", "/v1/audio/speech", {"audio_url": "https://cdn.example.test/voice.mp3"}),
        ("openai_compatible", ModelCapability.MUSIC, "music", "/v1/audio/music/generations", {"url": "https://cdn.example.test/music.mp3"}),
    ],
)
def test_audio_generation_posts_provider_contract_and_returns_asset_url(kind, capability, job_kind, path, response) -> None:
    registry, provider = make_provider(kind, capability)
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers["authorization"]
        captured["json"] = request.read().decode()
        return httpx.Response(200, json=response)

    job = MediaJobLedger().create(job_kind, "student-001", organization_id="org-001", prompt="海洋主题音频")
    result = MediaProviderGateway(registry, httpx.Client(transport=httpx.MockTransport(handler))).submit(provider, job)

    assert result.state == "succeeded"
    assert result.preview_url == next(iter(response.values()))
    assert captured["path"] == path
    assert captured["authorization"] == "Bearer audio-secret"
    assert '"model":"audio-model"' in captured["json"]


def test_audio_generation_rejects_response_without_url() -> None:
    registry, provider = make_provider("custom", ModelCapability.TEXT_TO_SPEECH)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ok"})))
    job = MediaJobLedger().create("voice", "student-001", organization_id="org-001", prompt="朗读这句话")

    with pytest.raises(ValueError, match="no audio URL"):
        MediaProviderGateway(registry, client).submit(provider, job)


def test_audio_generation_accepts_provider_base64_payload() -> None:
    registry, provider = make_provider("custom", ModelCapability.TEXT_TO_SPEECH)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"base64": "AQI="})))
    job = MediaJobLedger().create("voice", "student-001", organization_id="org-001", prompt="朗读这句话")

    result = MediaProviderGateway(registry, client).submit(provider, job)

    assert result.preview_url == "data:audio/mpeg;base64,AQI="


def test_music_generation_extracts_lyrics_and_duration() -> None:
    registry, provider = make_provider("custom", ModelCapability.MUSIC)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"url": "https://cdn.example.test/song.mp3", "lyrics": "第一行\n第二行"}], "duration": 37})))
    job = MediaJobLedger().create("music", "student-001", organization_id="org-001", prompt="童话", title="星星歌")

    result = MediaProviderGateway(registry, client).submit(provider, job)

    assert result.preview_url == "https://cdn.example.test/song.mp3"
    assert result.lyrics == "第一行\n第二行"
    assert result.duration_seconds == 37


def test_music_generation_without_lyrics_returns_empty_optional_metadata() -> None:
    registry, provider = make_provider("custom", ModelCapability.MUSIC)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"audio_url": "https://cdn.example.test/song.mp3"})))
    job = MediaJobLedger().create("music", "student-001", organization_id="org-001", prompt="童话")

    result = MediaProviderGateway(registry, client).submit(provider, job)

    assert result.lyrics == ""
    assert result.duration_seconds is None


def test_qwen_fun_music_uses_documented_request_and_parses_nested_audio() -> None:
    registry, original = make_provider("qwen", ModelCapability.MUSIC)
    provider = ModelProvider(original.provider_id, original.organization_id, original.capability, original.region, original.priority, original.api_key, provider_kind="qwen", model_id="fun-music-v1", base_url="https://dashscope.aliyuncs.com/api/v1")
    registry.register(provider)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output": {"audio": {"url": "https://cdn.example.test/song.mp3"}, "extra_info": {"lyrics": "真实歌词"}}, "usage": {"duration": 56}})

    job = MediaJobLedger().create("music", "student-001", organization_id="org-001", prompt="童话歌曲", lyrics="我写的歌词")
    result = MediaProviderGateway(registry, httpx.Client(transport=httpx.MockTransport(handler))).submit(provider, job)

    assert requests[0].url.path == "/api/v1/services/audio/music/generation"
    assert json.loads(requests[0].content) == {"model": "fun-music-v1", "input": {"lyrics": "我写的歌词"}}
    assert result.preview_url == "https://cdn.example.test/song.mp3"
    assert result.lyrics == "真实歌词"
    assert result.duration_seconds == 56


def test_doubao_image_uses_requested_ratio_as_pixel_size() -> None:
    registry, original = make_provider("doubao", ModelCapability.IMAGE)
    provider = ModelProvider(original.provider_id, original.organization_id, original.capability, original.region, original.priority, original.api_key, provider_kind="doubao", model_id="doubao-seedream-4-0", base_url="https://ark.cn-beijing.volces.com/api/v3")
    registry.register(provider)
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.test/image.png"}]})

    job = MediaJobLedger().create("image", "student-001", prompt="星空", aspect_ratio="3:4", reference_image_url="https://cdn.example.test/reference.png")
    MediaProviderGateway(registry, httpx.Client(transport=httpx.MockTransport(handler))).submit(provider, job)

    assert captured[0]["size"] == "1728x2304"
    assert captured[0]["image"] == "https://cdn.example.test/reference.png"
    assert "image_url" not in captured[0]


def test_video_submit_uses_selected_ratio_and_duration() -> None:
    registry, provider = make_provider("custom", ModelCapability.VIDEO)
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "video-task-1"})

    job = MediaJobLedger().create("video", "student-001", prompt="星空", aspect_ratio="9:16", video_duration_seconds=10)
    result = MediaProviderGateway(registry, httpx.Client(transport=httpx.MockTransport(handler))).submit(provider, job)

    assert result.external_task_id == "video-task-1"
    assert captured[0]["ratio"] == "9:16"
    assert captured[0]["duration"] == 10


@pytest.mark.parametrize("kind", ["image", "video"])
def test_doubao_receives_uploaded_local_reference_as_data_uri(kind, tmp_path, monkeypatch) -> None:
    import base64

    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    reference = tmp_path / "references" / "org-001" / "student-001" / "Abcdefghijk.png"
    reference.parent.mkdir(parents=True)
    payload = b"\x89PNG\r\n\x1a\nexample-image"
    reference.write_bytes(payload)
    registry, original = make_provider("doubao", ModelCapability.IMAGE if kind == "image" else ModelCapability.VIDEO)
    provider = ModelProvider(original.provider_id, original.organization_id, original.capability, original.region, original.priority, original.api_key, provider_kind="doubao", model_id="doubao-media-model", base_url="https://ark.cn-beijing.volces.com/api/v3")
    registry.register(provider)
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.test/image.png"}]} if kind == "image" else {"id": "task-1"})

    job = MediaJobLedger().create(kind, "student-001", organization_id="org-001", prompt="星空", reference_image_url="http://localhost:8000/generated-assets/references/org-001/student-001/Abcdefghijk.png")
    MediaProviderGateway(registry, httpx.Client(transport=httpx.MockTransport(handler))).submit(provider, job)

    expected = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    actual = captured[0]["image"] if kind == "image" else captured[0]["content"][1]["image_url"]["url"]
    assert actual == expected
