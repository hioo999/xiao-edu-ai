import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def test_course_upload_rejects_executable_content_before_storage() -> None:
    auth = AuthService({"teacher": UserRecord("teacher-1", "org-1", "teacher", hash_password("teacher-password"))})
    client = TestClient(create_app(auth_service=auth))
    login = client.post("/auth/login", json={"username": "teacher", "password": "teacher-password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    assert client.post("/courses", headers=headers, json={"courseId": "course-1", "title": "安全课"}).status_code == 200

    response = client.post("/courses/course-1/materials", headers=headers, files={"file": ("lesson.pdf", b"MZ malicious", "application/pdf")})

    assert response.status_code == 422
    assert "executable" in response.json()["detail"]
