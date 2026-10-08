import httpx
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
