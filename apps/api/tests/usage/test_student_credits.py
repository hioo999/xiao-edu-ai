import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import ModelGateway
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault
from apps.api.app.usage.service import QuotaExceeded, UsageLedger


def credit_client(initial_credits: int):
    auth = AuthService({"admin": UserRecord("admin", "org-1", "platform_admin", hash_password("admin-password"))})
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(ModelProvider("text-1", "org-1", ModelCapability.TEXT, "domestic", 1, "private-key", provider_kind="deepseek", model_id="test-model"))
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "一段回答"}}], "usage": {"prompt_tokens": 200, "completion_tokens": 100}})

    usage = UsageLedger({})
    client = TestClient(create_app(auth, registry, model_gateway=ModelGateway(registry, httpx.Client(transport=httpx.MockTransport(respond))), usage_ledger=usage))
    admin = client.post("/auth/admin/login", json={"username": "admin", "password": "admin-password"}).json()
    admin_headers = {"Authorization": f"Bearer {admin['accessToken']}"}
    created = client.post("/organizations/org-1/students/batch", headers=admin_headers, json={"prefix": "learner", "count": 1, "classId": "class-1", "initialPassword": "student-password", "initialCredits": initial_credits})
    assert created.status_code == 200
    assert created.json()["students"][0]["initialCredits"] == initial_credits
    student = client.post("/auth/login", json={"username": "learner-001", "password": "student-password"}).json()
    student_headers = {"Authorization": f"Bearer {student['accessToken']}"}
    return client, admin_headers, student_headers, calls


def test_student_text_uses_provider_token_usage_and_refunds_unused_reservation() -> None:
    client, _, student_headers, calls = credit_client(10)
    generated = client.post("/models/text/generate", headers=student_headers, json={"prompt": "写一段故事"})
    balance = client.get("/usage/credits/mine", headers=student_headers).json()
    assert generated.status_code == 200
    assert len(calls) == 1
    assert balance == {"configured": True, "granted": 10, "spent": 1, "reserved": 0, "balance": 9}


def test_insufficient_credits_prevent_provider_call() -> None:
    client, _, student_headers, calls = credit_client(0)
    generated = client.post("/models/text/generate", headers=student_headers, json={"prompt": "写一段故事"})
    assert generated.status_code == 429
    assert calls == []


def test_admin_can_grant_student_credits_after_account_creation() -> None:
    client, admin_headers, student_headers, calls = credit_client(0)
    blocked = client.post("/models/text/generate", headers=student_headers, json={"prompt": "写一段故事"})
    assert blocked.status_code == 429
    student_id = client.get("/auth/me", headers=student_headers).json()["userId"]
    granted = client.post(f"/usage/students/{student_id}/credits", headers=admin_headers, json={"amount": 10})
    assert granted.status_code == 200
    assert granted.json()["balance"] == 10
    generated = client.post("/models/text/generate", headers=student_headers, json={"prompt": "写一段故事"})
    assert generated.status_code == 200
    assert len(calls) == 1
    assert client.get("/usage/credits/mine", headers=student_headers).json()["balance"] == 9


def test_media_credit_reservation_settles_on_success_and_refunds_on_failure() -> None:
    client, admin_headers, student_headers, _ = credit_client(20)
    first = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "星空"})
    assert first.status_code == 202
    assert client.get("/usage/credits/mine", headers=student_headers).json()["balance"] == 12
    client.post(f"/media/jobs/{first.json()['jobId']}/worker-update", headers=admin_headers, json={"state": "failed", "error": "provider failed"})
    assert client.get("/usage/credits/mine", headers=student_headers).json()["balance"] == 20
    second = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "海洋"})
    settled = client.post(f"/media/jobs/{second.json()['jobId']}/worker-update", headers=admin_headers, json={"state": "succeeded", "previewUrl": "https://example.test/image.png"})
    assert settled.status_code == 200
    assert client.get("/usage/credits/mine", headers=student_headers).json()["spent"] == 8


def test_sqlite_credit_reservations_are_shared_between_processes(tmp_path) -> None:
    path = tmp_path / "platform.db"
    first, second = UsageLedger({}, path), UsageLedger({}, path)
    first.set_limit("student", "learner-1", "credits", 10)
    first.reserve("student", "learner-1", "credits", 8, reservation_id="job-1-credits")
    with pytest.raises(QuotaExceeded):
        second.reserve("student", "learner-1", "credits", 8, reservation_id="job-2-credits")
    second.finalize("job-1-credits")
    assert first.summary("student", "learner-1") == [{"metric": "credits", "limit": 10, "used": 8, "reserved": 0}]
