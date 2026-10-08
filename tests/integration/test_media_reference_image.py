import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def test_student_uploads_reference_image_and_attaches_it_to_media_job() -> None:
    auth = AuthService({"student": UserRecord("student-1", "org-1", "student", hash_password("student-password"))})
    client = TestClient(create_app(auth_service=auth))
    login = client.post("/auth/login", json={"username": "student", "password": "student-password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    uploaded = client.post("/media/jobs/reference-images", headers=headers, files={"file": ("turtle.png", b"\x89PNG\r\n\x1a\nimage", "image/png")})
    job = client.post("/media/jobs", headers=headers, json={"kind": "video", "prompt": "小海龟游泳", "referenceImageUrl": uploaded.json()["referenceImageUrl"]})

    assert uploaded.status_code == 200
    assert "/generated-assets/references/org-1/student-1/" in uploaded.json()["referenceImageUrl"]
    assert job.status_code == 202


def test_reference_image_rejects_invalid_file() -> None:
    auth = AuthService({"student": UserRecord("student-1", "org-1", "student", hash_password("student-password"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "student", "password": "student-password"}).json()["accessToken"]

    response = client.post("/media/jobs/reference-images", headers={"Authorization": f"Bearer {token}"}, files={"file": ("unsafe.exe", b"MZ", "application/octet-stream")})

    assert response.status_code == 422


def test_media_job_rejects_untrusted_reference_url() -> None:
    auth = AuthService({"student": UserRecord("student-1", "org-1", "student", hash_password("student-password"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "student", "password": "student-password"}).json()["accessToken"]

    response = client.post("/media/jobs", headers={"Authorization": f"Bearer {token}"}, json={"kind": "video", "prompt": "测试", "referenceImageUrl": "https://untrusted.example/image.png"})

    assert response.status_code == 422
    assert "current student" in response.json()["detail"]
