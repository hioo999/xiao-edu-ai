import httpx
import pytest

from cryptography.fernet import Fernet

from apps.api.app.models.gateway import ModelGateway
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


def registry_with(provider: ModelProvider) -> ProviderRegistry:
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(provider)
    return registry


def test_deepseek_text_request_uses_server_side_secret() -> None:
    provider = ModelProvider(
        provider_id="deepseek-classroom",
        organization_id=None,
        capability=ModelCapability.TEXT,
        region="domestic",
        priority=1,
        api_key="deepseek-private-key",
        provider_kind="deepseek",
        model_id="deepseek-chat",
    )
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = request.json() if hasattr(request, "json") else request.content
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好，小朋友！"}}]})

    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(handler)))

    result = gateway.generate_text("org-001", "请介绍太阳系")

    assert result.content == "你好，小朋友！"
    assert result.provider_id == "deepseek-classroom"
    assert captured["authorization"] == "Bearer deepseek-private-key"
    assert "请介绍太阳系".encode() in captured["body"]


def test_unsupported_provider_never_makes_a_network_request() -> None:
    provider = ModelProvider(
        provider_id="unknown-provider",
        organization_id=None,
        capability=ModelCapability.TEXT,
        region="domestic",
        priority=1,
        api_key="private-key",
        provider_kind="unknown",
        model_id="unknown-model",
    )
    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError()))))

    try:
        gateway.generate_text("org-001", "hello")
    except ValueError as exc:
        assert "unsupported provider" in str(exc)
    else:
        raise AssertionError("unsupported provider must fail")


def test_model_discovery_uses_server_side_secret_and_returns_provider_models() -> None:
    provider = ModelProvider("deepseek-classroom", None, ModelCapability.TEXT, "domestic", 1, "deepseek-private-key", provider_kind="deepseek", model_id="deepseek-chat")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        assert request.url.path == "/models"
        return httpx.Response(200, json={"data": [{"id": "deepseek-flash", "name": "DeepSeek Flash"}, {"id": "deepseek-v4-pro"}]})

    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(handler)))

    models = gateway.discover_models("deepseek-classroom")

    assert models[0].model_id == "deepseek-flash"
    assert models[0].display_name == "DeepSeek Flash"
    assert models[1].display_name == "deepseek-v4-pro"
    assert captured["authorization"] == "Bearer deepseek-private-key"


@pytest.mark.parametrize("provider_kind", ["deepseek", "qwen", "zhipu", "custom"])
def test_openai_compatible_connection_uses_minimal_generation(provider_kind: str) -> None:
    provider = ModelProvider("provider-classroom", None, ModelCapability.TEXT, "domestic", 1, "provider-private-key", provider_kind=provider_kind, model_id="model-flash")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = request.content.decode()
        assert request.method == "POST"
        assert request.url.path == "/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(handler)))

    result = gateway.test_connection("provider-classroom")

    assert captured["authorization"] == "Bearer provider-private-key"
    assert '"max_tokens":1' in captured["body"]
    assert result.status == "connected"


def test_doubao_text_connection_uses_minimal_chat_request() -> None:
    provider = ModelProvider("doubao-classroom", None, ModelCapability.TEXT, "domestic", 1, "doubao-private-key", provider_kind="doubao", model_id="doubao-seed-2-1-pro-260628", base_url="https://ark.cn-beijing.volces.com/api/v3")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = request.content
        assert request.method == "POST"
        assert request.url.path == "/api/v3/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(handler)))

    result = gateway.test_connection("doubao-classroom")

    assert captured["authorization"] == "Bearer doubao-private-key"
    assert b'"max_tokens":1' in captured["body"]
    assert result.status == "connected"


@pytest.mark.parametrize("capability", [ModelCapability.IMAGE, ModelCapability.VIDEO])
def test_doubao_media_connection_requires_an_actual_generation(capability: ModelCapability) -> None:
    provider = ModelProvider("doubao-media", None, capability, "domestic", 1, "doubao-private-key", provider_kind="doubao", model_id="endpoint-id", base_url="https://ark.cn-beijing.volces.com/api/v3")
    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError("must not make a misleading request")))))

    result = gateway.test_connection("doubao-media")

    assert result.status == "verification_required"
    assert "实际生成验证" in result.message


@pytest.mark.parametrize("status_code", [401, 403, 404, 429, 500])
def test_connection_surfaces_provider_http_failures(status_code: int) -> None:
    provider = ModelProvider("failing-provider", None, ModelCapability.TEXT, "domestic", 1, "private-key", provider_kind="deepseek", model_id="model")
    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status_code, request=request))))

    with pytest.raises(httpx.HTTPStatusError) as error:
        gateway.test_connection("failing-provider")

    assert error.value.response.status_code == status_code


def test_connection_surfaces_network_failure() -> None:
    provider = ModelProvider("offline-provider", None, ModelCapability.TEXT, "domestic", 1, "private-key", provider_kind="deepseek", model_id="model")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unavailable", request=request)

    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(httpx.ConnectError):
        gateway.test_connection("offline-provider")


def test_doubao_connection_rejects_an_invalid_success_response() -> None:
    provider = ModelProvider("doubao-invalid", None, ModelCapability.TEXT, "domestic", 1, "doubao-private-key", provider_kind="doubao", model_id="model", base_url="https://ark.cn-beijing.volces.com/api/v3")
    gateway = ModelGateway(registry_with(provider), httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"id": "missing-choices"}, request=request))))

    with pytest.raises(ValueError, match="invalid text response"):
        gateway.test_connection("doubao-invalid")


def test_gateway_falls_back_to_next_text_provider_after_primary_failure() -> None:
    primary = ModelProvider("primary", None, ModelCapability.TEXT, "domestic", 1, "primary-key", provider_kind="custom", model_id="primary-model", base_url="https://primary.example")
    backup = ModelProvider("backup", None, ModelCapability.TEXT, "domestic", 2, "backup-key", provider_kind="custom", model_id="backup-model", base_url="https://backup.example")
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(primary)
    registry.register(backup)

    def handler(request: httpx.Request) -> httpx.Response:
        if "primary" in str(request.url):
            return httpx.Response(429, json={"error": "quota exceeded"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "备用模型响应"}}]})

    result = ModelGateway(registry, httpx.Client(transport=httpx.MockTransport(handler))).generate_text("org-001", "hello")

    assert result.provider_id == "backup"
    assert result.content == "备用模型响应"
