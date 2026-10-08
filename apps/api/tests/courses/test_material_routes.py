from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.courses.storage import CourseMaterialStore
from apps.api.app.main import create_app
from apps.api.app.models.registry import ProviderRegistry, SecretVault


def test_teacher_can_upload_and_list_course_material(tmp_path: Path) -> None:
    service = AuthService({"teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("teacher-password"))})
    client = TestClient(create_app(service, ProviderRegistry(SecretVault(Fernet.generate_key())), course_material_store=CourseMaterialStore(tmp_path)))
    login = client.post("/auth/login", json={"username": "teacher-001", "password": "teacher-password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    saved = client.post("/courses", headers=headers, json={"courseId": "course-001", "title": "海洋课"})

    upload = client.post("/courses/course-001/materials", headers=headers, files={"file": ("lesson.pdf", b"%PDF-1.7\ndemo lesson", "application/pdf")})
    listed = client.get("/courses/course-001/materials", headers=headers)

    assert saved.status_code == 200
    assert upload.status_code == 200
    assert upload.json()["filename"] == "lesson.pdf"
    assert listed.json()["materials"][0]["size"] == len(b"%PDF-1.7\ndemo lesson")
