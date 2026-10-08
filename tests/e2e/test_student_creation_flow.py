from fastapi.testclient import TestClient
import pytest

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration


pytestmark = pytest.mark.e2e


class E2EFakeGateway:
    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        return TextGeneration(
            provider_id="e2e-provider",
            model_id="e2e-model",
            content=f"网页方案：{prompt}",
        )


def test_student_can_complete_login_creation_and_media_flow() -> None:
    auth = AuthService(
        users={
            "student-e2e": UserRecord(
                user_id="student-e2e",
                organization_id="org-e2e",
                role="student",
                password_hash=hash_password("password"),
            )
        }
    )
    client = TestClient(create_app(auth, model_gateway=E2EFakeGateway()))

    login = client.post("/auth/login", json={"username": "student-e2e", "password": "password"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    me = client.get("/auth/me", headers=headers)
    generated = client.post(
        "/models/text/generate",
        headers=headers,
        json={"prompt": "生成一个海洋主题网页"},
    )
    media = client.post(
        "/media/jobs",
        headers=headers,
        json={"kind": "image", "prompt": "海洋主题封面"},
    )
    html = client.post(
        "/projects/student-project/html/generate",
        headers=headers,
        json={"prompt": "生成一个海洋主题网页"},
    )
    jobs = client.get("/media/jobs", headers=headers)

    assert me.json() == {"userId": "student-e2e", "organizationId": "org-e2e", "role": "student", "classId": None}
    assert generated.json() == {
        "content": "网页方案：生成一个海洋主题网页",
        "providerId": "e2e-provider",
        "modelId": "e2e-model",
    }
    assert media.status_code == 202
    assert jobs.json()["jobs"][0]["jobId"] == media.json()["jobId"]
    assert html.status_code == 200
    assert html.json()["currentVersion"]["html"].startswith("<!doctype html>")
