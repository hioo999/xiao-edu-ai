import httpx
import pytest
from cryptography.fernet import Fernet

from apps.api.app.models.gateway import ModelGateway
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


def make_registry(*providers: ModelProvider) -> ProviderRegistry:
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    for provider in providers:
        registry.register(provider)
    return registry


def provider(provider_id: str = "primary", *, priority: int = 1, kind: str = "custom") -> ModelProvider:
    return ModelProvider(
        provider_id=provider_id,
        organization_id=None,
        capability=ModelCapability.TEXT,
        region="domestic",
        priority=priority,
        api_key=f"secret-{provider_id}",
        provider_kind=kind,
        model_id=f"model-{provider_id}",
        base_url=f"https://{provider_id}.example",
    )


pytestmark = pytest.mark.unit


def test_generate_text_parses_openai_compatible_response_without_leaking_secret() -> None:
    current_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_request
        current_request = request
        return httpx.Response(200, json={"choices": [{"message": {"content": "生成成功"}}]})

    gateway = ModelGateway(
        make_registry(provider()),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = gateway.generate_text("org-001", "做一个网页")

    assert result.content == "生成成功"
    assert current_request is not None
    assert current_request.headers["authorization"] == "Bearer secret-primary"
    assert current_request.url.path == "/chat/completions"


@pytest.mark.parametrize(
    "payload",
    [{}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}],
)
def test_generate_text_rejects_invalid_provider_payload(payload: dict[str, object]) -> None:
    gateway = ModelGateway(
        make_registry(provider()),
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))),
    )

    with pytest.raises(ValueError, match="all text model providers are unavailable"):
        gateway.generate_text("org-001", "hello")


def test_generate_text_falls_back_when_primary_provider_fails() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host or "")
        if request.url.host == "primary.example":
            return httpx.Response(429, request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "备用响应"}}]})

    gateway = ModelGateway(
        make_registry(provider(), provider("backup", priority=2)),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = gateway.generate_text("org-001", "hello")

    assert result.provider_id == "backup"
    assert calls == ["primary.example", "backup.example"]


def test_discover_models_skips_malformed_entries() -> None:
    gateway = ModelGateway(
        make_registry(provider()),
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"data": [{"id": "model-a", "name": "模型 A"}, {"name": "缺少 id"}, "bad"]},
                )
            )
        ),
    )

    models = gateway.discover_models("primary")

    assert [(item.model_id, item.display_name) for item in models] == [("model-a", "模型 A")]
