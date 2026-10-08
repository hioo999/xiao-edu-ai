import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": "teacher-password"})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_course_material_requires_an_owned_course() -> None:
    auth = AuthService(
        {
            "teacher-one": UserRecord("teacher-1", "org-1", "teacher", hash_password("teacher-password")),
            "teacher-two": UserRecord("teacher-2", "org-2", "teacher", hash_password("teacher-password")),
        }
    )
    client = TestClient(create_app(auth_service=auth))
    owner_headers = _login(client, "teacher-one")
    other_headers = _login(client, "teacher-two")
    assert client.post("/courses", headers=owner_headers, json={"courseId": "ocean-course", "title": "海洋创作"}).status_code == 200

    material = ("lesson.pdf", b"%PDF-1.7\nlesson", "application/pdf")
    missing = client.post("/courses/unknown/materials", headers=owner_headers, files={"file": material})
    cross_tenant = client.post("/courses/ocean-course/materials", headers=other_headers, files={"file": material})
    owner = client.post("/courses/ocean-course/materials", headers=owner_headers, files={"file": material})

    assert missing.status_code == 404
    assert cross_tenant.status_code == 404
    assert owner.status_code == 200
