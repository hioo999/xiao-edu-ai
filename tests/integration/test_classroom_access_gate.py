import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration


pytestmark = pytest.mark.integration


class FakeGateway:
    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        return TextGeneration("fake", "fake-model", "生成成功")


def test_paused_classroom_blocks_student_ai_generation_until_opened() -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-a")})
    classrooms = AssistanceManager()
    classrooms.create("class-a", "org-001")
    client = TestClient(create_app(auth_service=auth, assistance_manager=classrooms, model_gateway=FakeGateway()))
    login = client.post("/auth/login", json={"username": "student", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    paused = client.post("/models/text/generate", headers=headers, json={"prompt": "生成一个网页"})
    classrooms.open("class-a")
    opened = client.post("/models/text/generate", headers=headers, json={"prompt": "生成一个网页"})

    assert paused.status_code == 423
    assert opened.status_code == 200
