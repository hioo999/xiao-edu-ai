import os

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.e2e


def test_teacher_handover_keeps_student_work_and_allows_replacement_to_review(tmp_path, monkeypatch):
    for variable in ("WORK_ARTIFACT_STORAGE_PATH", "WORK_INTERACTION_STORAGE_PATH", "SHOWCASE_MEDIA_STORAGE_PATH", "LEARNING_STORAGE_PATH", "DEPLOYMENT_STORAGE_PATH"):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))
    auth = AuthService({"admin": UserRecord("admin", "school", "organization_admin", hash_password("password123"))}, storage_path=os.environ["PLATFORM_DB_PATH"])
    client = TestClient(create_app(auth_service=auth))

    def login(username):
        endpoint = "/auth/admin/login" if username == "admin" else "/auth/login"
        response = client.post(endpoint, json={"username": username, "password": "password123"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    admin = login("admin")
    teachers = []
    for username in ("source", "replacement"):
        created = client.post("/organizations/school/staff", headers=admin, json={"username": username, "password": "password123", "role": "teacher"})
        assert created.status_code == 200
        teachers.append(created.json()["userId"])
    assert client.post("/classrooms", headers=admin, json={"classId": "class-a", "teacherIds": [teachers[0]]}).status_code == 200
    students = client.post("/organizations/school/students/batch", headers=admin, json={"prefix": "pupil", "count": 1, "classId": "class-a", "initialPassword": "password123"}).json()["students"]
    source, replacement, student = login("source"), login("replacement"), login(students[0]["username"])
    assert client.post("/classrooms/class-a/open", headers=source).status_code == 200
    assert client.post("/courses", headers=source, json={"courseId": "lesson", "title": "魔法书课程"}).status_code == 200
    assert client.post("/courses/lesson/publish", headers=source, json={"classId": "class-a"}).status_code == 200
    created_work = client.post("/works", headers=student, json={"projectId": "story", "kind": "text", "title": "魔法书", "content": "魔法书里住着小精灵。"})
    assert created_work.status_code == 200
    work_id = created_work.json()["assetId"]
    assert client.get(f"/works/{work_id}", headers=replacement).status_code == 403
    handed_over = client.post("/organizations/school/staff/source/handover", headers=admin, json={"replacementUserId": teachers[1], "reason": "原老师离职，接任老师继续授课"})
    assert handed_over.status_code == 200
    assert client.get("/auth/me", headers=source).status_code == 401
    assert client.get(f"/works/{work_id}", headers=replacement).status_code == 200
    assert client.post(f"/works/{work_id}/comments", headers=replacement, json={"body": "我会继续帮助你完善魔法书"}).status_code == 200
    assert client.get("/works/mine", headers=student).json()["works"][0]["ownerUserId"] == students[0]["username"]
    assert client.get("/courses/classrooms/class-a/published", headers=student).json()["courses"][0]["title"] == "魔法书课程"
