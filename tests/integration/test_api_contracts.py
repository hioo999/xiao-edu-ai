from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
import pytest

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import ConnectionCheck, TextGeneration
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault


pytestmark = pytest.mark.integration


class FakeGateway:
    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        return TextGeneration("fake-text", "fake-model", f"已生成：{prompt}")


def make_service() -> AuthService:
    return AuthService(
        users={
            "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
            "admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
        }
    )


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": "password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def make_client() -> TestClient:
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(ModelProvider("provider-1", None, ModelCapability.TEXT, "domestic", 1, "server-secret", provider_kind="custom", model_id="model-1"))
    return TestClient(create_app(make_service(), provider_registry=registry, model_gateway=FakeGateway()))


def test_health_and_readiness_return_stable_json_contracts() -> None:
    client = make_client()

    health = client.get("/health")
    ready = client.get("/health/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "storage": "ok"}


def test_auth_login_me_and_logout_contract() -> None:
    client = make_client()
    headers = login(client, "student")

    me = client.get("/auth/me", headers=headers)
    logged_out = client.post("/auth/logout", headers=headers)
    after_logout = client.get("/auth/me", headers=headers)

    assert me.json() == {"userId": "student-001", "organizationId": "org-001", "role": "student", "classId": None}
    assert logged_out.json() == {"status": "logged_out"}
    assert after_logout.status_code == 401


def test_text_generation_returns_content_provider_and_model_ids() -> None:
    client = make_client()
    response = client.post("/models/text/generate", headers=login(client, "student"), json={"prompt": "做一个太阳系网页"})

    assert response.status_code == 200
    assert response.json() == {
        "content": "已生成：做一个太阳系网页",
        "providerId": "fake-text",
        "modelId": "fake-model",
    }


def test_text_generation_rejects_empty_prompt_and_requires_authentication() -> None:
    client = make_client()

    assert client.post("/models/text/generate", json={"prompt": "   "}).status_code == 401
    response = client.post("/models/text/generate", headers=login(client, "student"), json={"prompt": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == "prompt is required"


def test_admin_provider_listing_redacts_api_key() -> None:
    client = make_client()
    response = client.get("/models/providers", headers=login(client, "admin"))

    assert response.status_code == 200
    provider = response.json()["providers"][0]
    assert provider["api_key"] == "••••cret"
    assert "server-secret" not in response.text


def test_media_job_contract_and_student_isolation() -> None:
    client = make_client()
    headers = login(client, "student")

    created = client.post("/media/jobs", headers=headers, json={"kind": "image", "prompt": "一只太空猫"})
    job_id = created.json()["jobId"]
    detail = client.get(f"/media/jobs/{job_id}", headers=headers)
    listed = client.get("/media/jobs", headers=headers)

    assert created.status_code == 202
    assert set(created.json()) == {"jobId", "state", "statusUrl"}
    assert detail.status_code == 200
    assert set(detail.json()) >= {"jobId", "kind", "state", "progress"}
    assert listed.status_code == 200
    assert listed.json()["jobs"][0]["jobId"] == job_id


def test_admin_can_save_provider_and_connection_test_contract() -> None:
    client = make_client()
    headers = login(client, "admin")
    saved = client.post(
        "/models/providers",
        headers=headers,
        json={"providerId": "new-provider", "capability": "text", "region": "domestic", "apiKey": "new-secret", "modelId": "model-new"},
    )

    assert saved.status_code == 200
    assert saved.json() == {"providerId": "new-provider", "status": "registered"}


def test_default_html_workspace_is_wired_to_the_model_gateway() -> None:
    client = TestClient(create_app(make_service(), model_gateway=FakeGateway()))

    response = client.post(
        "/projects/project-001/html/generate",
        headers=login(client, "student"),
        json={"prompt": "做一个海洋网页"},
    )

    assert response.status_code == 200
    assert response.json()["currentVersion"]["html"].startswith("<!doctype html>")
    assert len(response.json()["currentVersion"]["teachingSteps"]) == 3
