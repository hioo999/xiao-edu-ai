from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration
from apps.api.app.models.calls import ModelCallLog
from apps.api.app.usage.service import UsageLedger


class FakeGateway:
    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        assert organization_id == "org-001"
        assert prompt == "帮我做一个太空网页"
        return TextGeneration("platform-deepseek-text", "deepseek-chat", "先从首页开始吧！")


def test_student_can_generate_text_through_platform_gateway() -> None:
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    client = TestClient(create_app(service, model_gateway=FakeGateway()))
    login = client.post("/auth/login", json={"username": "student-001", "password": "password"})

    response = client.post(
        "/models/text/generate",
        headers={"Authorization": f"Bearer {login.json()['accessToken']}"},
        json={"prompt": "帮我做一个太空网页"},
    )

    assert response.status_code == 200
    assert response.json() == {"content": "先从首页开始吧！", "providerId": "platform-deepseek-text", "modelId": "deepseek-chat"}


def test_admin_can_read_recent_model_calls() -> None:
    service = AuthService(users={"admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password"))})
    calls = ModelCallLog()
    calls.record("org-001", "deepseek-primary", "text", "succeeded")
    client = TestClient(create_app(service, model_call_log=calls))
    login = client.post("/auth/login", json={"username": "admin", "password": "password"})

    response = client.get("/models/calls", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})

    assert response.status_code == 200
    assert response.json()["calls"][0]["provider_id"] == "deepseek-primary"


def test_model_call_log_filters_and_paginates() -> None:
    calls = ModelCallLog()
    calls.record("org-001", "provider-a", "text", "failed")
    calls.record("org-001", "provider-b", "image", "succeeded")
    calls.record("org-001", "provider-a", "text", "succeeded")

    result = calls.recent("org-001", limit=1, provider_id="provider-a", capability="text", outcome="succeeded")

    assert len(result) == 1
    assert result[0].provider_id == "provider-a"


def test_text_generation_reserves_and_finalizes_organization_quota() -> None:
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    usage = UsageLedger({("organization", "org-001", "text"): 1})
    client = TestClient(create_app(service, model_gateway=FakeGateway(), usage_ledger=usage))
    login = client.post("/auth/login", json={"username": "student-001", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    first = client.post("/models/text/generate", headers=headers, json={"prompt": "帮我做一个太空网页"})
    second = client.post("/models/text/generate", headers=headers, json={"prompt": "再做一个海洋网页"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert usage.committed("organization", "org-001", "text") == 1


def test_text_generation_uses_student_quota_before_organization_quota() -> None:
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    usage = UsageLedger({("student", "student-001", "text"): 0, ("organization", "org-001", "text"): 5})
    client = TestClient(create_app(service, model_gateway=FakeGateway(), usage_ledger=usage))
    login = client.post("/auth/login", json={"username": "student-001", "password": "password"})

    response = client.post("/models/text/generate", headers={"Authorization": f"Bearer {login.json()['accessToken']}"}, json={"prompt": "应该被学生额度拦截"})

    assert response.status_code == 429
    assert usage.committed("organization", "org-001", "text") == 0
