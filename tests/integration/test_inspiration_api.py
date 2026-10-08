import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def test_teacher_manages_case_and_student_can_recommend_and_favorite_it() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    client = TestClient(create_app(auth))
    teacher = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    student = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]
    teacher_headers = {"Authorization": f"Bearer {teacher}"}
    student_headers = {"Authorization": f"Bearer {student}"}

    saved = client.post("/inspiration", headers=teacher_headers, json={
        "title": "海洋故事网页", "gradeMin": 3, "gradeMax": 6, "interests": ["科学", "海洋"],
        "difficulty": "入门", "durationMinutes": 20, "prompt": "做一个会讲故事的海洋网页", "capability": "html",
    })
    case_id = saved.json()["caseId"]
    listed = client.get("/inspiration?grade=4&interests=海洋", headers=student_headers)
    favorite = client.post(f"/inspiration/{case_id}/favorite", headers=student_headers, json={"enabled": True})

    assert saved.status_code == 200
    assert listed.json()["cases"] == [{**saved.json(), "favorite": False}]
    assert favorite.json() == {"caseId": case_id, "favorite": True}
    assert client.get("/inspiration?grade=4", headers=student_headers).json()["cases"][0]["favorite"] is True


def test_student_cannot_create_inspiration_case() -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    client = TestClient(create_app(auth))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/inspiration", headers={"Authorization": f"Bearer {token}"}, json={"title": "test", "gradeMin": 3, "gradeMax": 3, "interests": ["art"], "difficulty": "入门", "durationMinutes": 10, "prompt": "test", "capability": "text"})

    assert response.status_code == 403
