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

def test_teacher_can_bind_material_to_a_specific_lesson(tmp_path: Path) -> None:
    service = AuthService({"teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("teacher-password"))})
    client = TestClient(create_app(service, ProviderRegistry(SecretVault(Fernet.generate_key())), course_material_store=CourseMaterialStore(tmp_path)))
    token = client.post("/auth/login", json={"username": "teacher-001", "password": "teacher-password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/courses", headers=headers, json={"courseId": "course-002", "title": "网页课", "lessons": [{"lessonId": "lesson-2", "title": "第二课", "content": "按钮", "sortOrder": 1, "required": True}]})
    response = client.post("/courses/course-002/materials?lessonId=lesson-2", headers=headers, files={"file": ("slides.pdf", b"%PDF-1.7 slides", "application/pdf")})
    assert response.status_code == 200
    assert response.json()["lessonId"] == "lesson-2"
    missing = client.post("/courses/course-002/materials?lessonId=missing", headers=headers, files={"file": ("slides.pdf", b"%PDF-1.7 slides", "application/pdf")})
    assert missing.status_code == 422


def test_course_rejects_duplicate_lessons_and_preserves_bound_materials(tmp_path: Path) -> None:
    service = AuthService({"teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("teacher-password"))})
    client = TestClient(create_app(service, ProviderRegistry(SecretVault(Fernet.generate_key())), course_material_store=CourseMaterialStore(tmp_path)))
    token = client.post("/auth/login", json={"username": "teacher-001", "password": "teacher-password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    lessons = [{"lessonId": "lesson-1", "title": "第一课"}, {"lessonId": "lesson-2", "title": "第二课"}]
    assert client.post("/courses", headers=headers, json={"courseId": "course-safe", "title": "安全课程", "lessons": lessons}).status_code == 200
    duplicate = client.post("/courses", headers=headers, json={"courseId": "course-duplicate", "title": "重复课时", "lessons": [{"lessonId": "same", "title": "一"}, {"lessonId": "same", "title": "二"}]})
    assert duplicate.status_code == 422
    client.post("/courses/course-safe/materials?lessonId=lesson-1", headers=headers, files={"file": ("slides.pdf", b"%PDF-1.7 slides", "application/pdf")})
    removed = client.post("/courses", headers=headers, json={"courseId": "course-safe", "title": "安全课程", "lessons": [{"lessonId": "lesson-2", "title": "第二课"}]})
    assert removed.status_code == 422


def test_review_keeps_independent_lessons(tmp_path: Path) -> None:
    users = {
        "teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("teacher-password")),
        "admin-001": UserRecord("admin-001", "org-001", "organization_admin", hash_password("admin-password")),
    }
    client = TestClient(create_app(AuthService(users), ProviderRegistry(SecretVault(Fernet.generate_key())), course_material_store=CourseMaterialStore(tmp_path)))
    teacher_token = client.post("/auth/login", json={"username": "teacher-001", "password": "teacher-password"}).json()["accessToken"]
    admin_token = client.post("/auth/admin/login", json={"username": "admin-001", "password": "admin-password"}).json()["accessToken"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    lessons = [{"lessonId": "lesson-1", "title": "第一课", "content": "画海龟", "sortOrder": 0, "required": True}]
    client.post("/courses", headers=teacher_headers, json={"courseId": "review-course", "title": "海洋创作", "studentFlow": ["画海龟"], "lessons": lessons})

    submitted = client.post("/courses/review-course/submit-review", headers=teacher_headers)
    approved = client.post("/courses/review-course/review/approve", headers=admin_headers, json={"note": "内容合适"})

    assert submitted.status_code == 200
    assert approved.status_code == 200
    assert submitted.json()["lessons"] == lessons
    assert approved.json()["lessons"] == lessons
