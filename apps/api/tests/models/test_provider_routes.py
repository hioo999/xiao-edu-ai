from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
import httpx

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import ModelGateway
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


def admin_client_with_provider(provider: ModelProvider, handler) -> tuple[TestClient, dict[str, str]]:
    service = AuthService(users={"admin-001": UserRecord(user_id="admin-001", organization_id="org-001", role="organization_admin", password_hash=hash_password("admin-password"))})
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(provider)
    client = TestClient(create_app(service, registry, model_gateway=ModelGateway(registry, httpx.Client(transport=httpx.MockTransport(handler)))))
    login = client.post("/auth/login", json={"username": "admin-001", "password": "admin-password"})
    return client, {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_provider_connection_reports_authentication_failure_safely() -> None:
    provider = ModelProvider("text-provider", "org-001", ModelCapability.TEXT, "domestic", 1, "private-key", provider_kind="deepseek", model_id="model")
    client, headers = admin_client_with_provider(provider, lambda request: httpx.Response(401, request=request))

    response = client.post("/models/providers/text-provider/test", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "服务商拒绝连接（HTTP 401）。请确认 API Key、模型和项目空间是否一致。"
    assert "private-key" not in response.text


def test_provider_connection_reports_network_failure_safely() -> None:
    provider = ModelProvider("text-provider", "org-001", ModelCapability.TEXT, "domestic", 1, "private-key", provider_kind="deepseek", model_id="model")

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unavailable", request=request)

    client, headers = admin_client_with_provider(provider, offline)

    response = client.post("/models/providers/text-provider/test", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "无法连接服务商，请检查 Base URL 或网络连通性。"


def test_provider_connection_reports_invalid_response_safely() -> None:
    provider = ModelProvider("doubao-text", "org-001", ModelCapability.TEXT, "domestic", 1, "private-key", provider_kind="doubao", model_id="model", base_url="https://ark.cn-beijing.volces.com/api/v3")
    client, headers = admin_client_with_provider(provider, lambda request: httpx.Response(200, json={"unexpected": "response"}, request=request))

    response = client.post("/models/providers/doubao-text/test", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "服务商返回了无法识别的响应。请检查模型名称和接口类型。"


def test_doubao_media_connection_requires_actual_generation() -> None:
    provider = ModelProvider("doubao-image", "org-001", ModelCapability.IMAGE, "domestic", 1, "private-key", provider_kind="doubao", model_id="endpoint-id", base_url="https://ark.cn-beijing.volces.com/api/v3")
    client, headers = admin_client_with_provider(provider, lambda _: (_ for _ in ()).throw(AssertionError("media health check must not make a request")))

    response = client.post("/models/providers/doubao-image/test", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "verification_required"
    assert "实际生成验证" in response.json()["message"]


def test_organization_admin_can_register_provider_without_reading_back_secret() -> None:
    service = AuthService(
        users={
            "admin-001": UserRecord(
                user_id="admin-001",
                organization_id="org-001",
                role="organization_admin",
                password_hash=hash_password("admin-password"),
            )
        }
    )
    client = TestClient(
        create_app(
            service,
            ProviderRegistry(SecretVault(Fernet.generate_key())),
        )
    )
    login = client.post(
        "/auth/login",
        json={"username": "admin-001", "password": "admin-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    register = client.post(
        "/models/providers",
        headers=headers,
        json={
            "providerId": "text-provider",
            "capability": "text",
            "region": "domestic",
            "apiKey": "sk-live-secret-1234",
        },
    )
    listed = client.get("/models/providers", headers=headers)

    assert register.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["providers"][0]["api_key"] == "••••1234"
    assert "sk-live-secret-1234" not in listed.text


def test_admin_can_update_provider_without_sending_key_and_delete_it() -> None:
    service = AuthService(users={"admin-001": UserRecord(user_id="admin-001", organization_id="org-001", role="organization_admin", password_hash=hash_password("admin-password"))})
    client = TestClient(create_app(service, ProviderRegistry(SecretVault(Fernet.generate_key()))))
    login = client.post("/auth/login", json={"username": "admin-001", "password": "admin-password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    create = client.post("/models/providers", headers=headers, json={"providerId": "image-primary", "capability": "image", "region": "domestic", "apiKey": "image-secret-1234", "modelId": "seedream", "priority": 1})
    update = client.post("/models/providers", headers=headers, json={"providerId": "image-primary", "capability": "image", "region": "domestic", "modelId": "seedream-v2", "priority": 2})
    listed = client.get("/models/providers", headers=headers)
    deleted = client.delete("/models/providers/image-primary", headers=headers)

    assert create.status_code == 200
    assert update.status_code == 200
    assert listed.json()["providers"][0]["model_id"] == "seedream-v2"
    assert listed.json()["providers"][0]["api_key"] == "••••1234"
    assert deleted.status_code == 200
    assert client.get("/models/providers", headers=headers).json()["providers"] == []
