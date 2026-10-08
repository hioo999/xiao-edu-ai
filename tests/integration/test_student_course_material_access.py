import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def _headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_student_only_reads_materials_published_to_own_class() -> None:
    auth = AuthService(
        {
            "teacher": UserRecord("teacher-1", "org-1", "teacher", hash_password("teacher-password")),
            "student-a": UserRecord("student-a", "org-1", "student", hash_password("student-password"), class_id="class-a"),
            "student-b": UserRecord("student-b", "org-1", "student", hash_password("student-password"), class_id="class-b"),
        }
    )
    client = TestClient(create_app(auth_service=auth))
    teacher = _headers(client, "teacher", "teacher-password")
    student_a = _headers(client, "student-a", "student-password")
    student_b = _headers(client, "student-b", "student-password")
    assert client.post("/courses", headers=teacher, json={"courseId": "course-a", "title": "海洋课"}).status_code == 200
    uploaded = client.post("/courses/course-a/materials", headers=teacher, files={"file": ("lesson.pdf", b"%PDF-1.7\nlesson", "application/pdf")})
    assert client.post("/courses/course-a/publish", headers=teacher, json={"classId": "class-a"}).status_code == 200
    material_id = uploaded.json()["materialId"]

    listed = client.get("/courses/classrooms/class-a/published/course-a/materials", headers=student_a)
    other_class = client.get("/courses/classrooms/class-a/published", headers=student_b)
    downloaded = client.get(f"/courses/materials/{material_id}/download", headers=student_a)
    denied_download = client.get(f"/courses/materials/{material_id}/download", headers=student_b)

    assert listed.status_code == 200
    assert listed.json()["materials"][0]["materialId"] == material_id
    assert other_class.status_code == 404
    assert downloaded.content == b"%PDF-1.7\nlesson"
    assert denied_download.status_code == 404
