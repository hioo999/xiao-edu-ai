from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.main import create_app


def _client(tmp_path):
    users = {
        "admin": UserRecord("admin", "school", "organization_admin", hash_password("password123")),
        "teacher-a": UserRecord("teacher-a", "school", "teacher", hash_password("password123")),
        "teacher-b": UserRecord("teacher-b", "school", "teacher", hash_password("password123")),
        "student": UserRecord("student", "school", "student", hash_password("password123"), class_id="class-a"),
    }
    auth = AuthService(users, storage_path=tmp_path / "platform.db")
    classrooms = AssistanceManager(tmp_path / "platform.db")
    classrooms.create("class-a", "school").teachers = {"teacher-a"}
    classrooms.create("class-b", "school").teachers = {"teacher-b"}
    app = create_app(auth_service=auth, assistance_manager=classrooms)
    client = TestClient(app)

    def login(username):
        response = client.post("/auth/login", json={"username": username, "password": "password123"})
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    return client, login


def test_admin_can_enroll_and_transfer_student_with_history(tmp_path):
    client, login = _client(tmp_path)
    admin = login("admin")

    enrolled = client.post("/classrooms/class-a/members", headers=admin, json={"studentId": "student"})
    assert enrolled.status_code == 200
    transferred = client.post("/classrooms/class-b/members", headers=admin, json={"studentId": "student", "reason": "换班"})
    assert transferred.status_code == 200
    assert transferred.json()["previousClassId"] == "class-a"
    history = client.get("/classrooms/students/student/memberships", headers=admin)
    assert history.status_code == 200
    assert [(item["classId"], item["active"]) for item in history.json()["memberships"]] == [("class-b", True), ("class-a", False)]


def test_teacher_assignment_has_role_and_expiry(tmp_path):
    client, login = _client(tmp_path)
    admin = login("admin")
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    response = client.put("/classrooms/class-a/staff", headers=admin, json={"assignments": [{"teacherId": "teacher-b", "role": "assistant", "validUntil": expires}]})
    assert response.status_code == 200
    assert response.json()["assignments"][0]["role"] == "assistant"
    assert client.get("/classrooms/class-a/staff", headers=admin).json()["assignments"][0]["teacherId"] == "teacher-b"


def test_teacher_cannot_transfer_or_enroll_students(tmp_path):
    client, login = _client(tmp_path)
    response = client.post("/classrooms/class-b/members", headers=login("teacher-a"), json={"studentId": "student"})
    assert response.status_code == 403
