import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.e2e


def test_admin_teacher_student_teaching_flow_and_permission_handover(tmp_path, monkeypatch):
    for variable, directory in (
        ("LEARNING_STORAGE_PATH", "learning"),
        ("WORK_ARTIFACT_STORAGE_PATH", "artifacts"),
        ("WORK_INTERACTION_STORAGE_PATH", "interactions"),
        ("DEPLOYMENT_STORAGE_PATH", "deployments"),
        ("SHOWCASE_MEDIA_STORAGE_PATH", "showcase"),
    ):
        monkeypatch.setenv(variable, str(tmp_path / directory))
    auth = AuthService({"admin": UserRecord("admin", "school", "organization_admin", hash_password("password123"))}, storage_path=tmp_path / "users.db")
    client = TestClient(create_app(auth_service=auth))

    def login(username):
        endpoint = "/auth/admin/login" if username == "admin" else "/auth/login"
        response = client.post(endpoint, json={"username": username, "password": "password123"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    admin = login("admin")
    teachers = []
    for username in ("teacher-a", "teacher-b"):
        response = client.post("/organizations/school/staff", headers=admin, json={"username": username, "password": "password123", "role": "teacher"})
        assert response.status_code == 200
        teachers.append(response.json()["userId"])
    assert client.post("/classrooms", headers=admin, json={"classId": "class-a", "teacherIds": [teachers[0]]}).status_code == 200
    batch = client.post("/organizations/school/students/batch", headers=admin, json={"prefix": "pupil", "count": 1, "classId": "class-a", "initialPassword": "password123"})
    assert batch.status_code == 200
    teacher = login("teacher-a")
    other_teacher = login("teacher-b")
    student = login(batch.json()["students"][0]["username"])
    assert client.post("/classrooms/class-a/open", headers=teacher).status_code == 200
    assert client.post("/courses", headers=teacher, json={"courseId": "lesson", "title": "魔法故事课", "teacherScript": "仅教师可见的逐字稿"}).status_code == 200
    assert client.post("/courses/lesson/publish", headers=teacher, json={"classId": "class-a"}).status_code == 200
    published = client.get("/courses/classrooms/class-a/published", headers=student)
    assert "teacherScript" not in published.json()["courses"][0]
    work_response = client.post("/works", headers=student, json={"projectId": "story", "kind": "text", "title": "魔法森林", "content": "森林里的小龙学会了分享。"})
    assert work_response.status_code == 200
    work_id = work_response.json()["assetId"]
    submission = client.post("/learning/courses/lesson/submissions", headers=student, json={"content": f"作品：{work_id}"})
    assert submission.status_code == 200
    submission_id = submission.json()["submissionId"]
    assert client.get("/works/review", headers=other_teacher).json()["works"] == []
    assert client.post(f"/works/{work_id}/review", headers=other_teacher, json={"state": "approved"}).status_code == 403
    assert client.post(f"/learning/submissions/{submission_id}/annotate", headers=teacher, json={"feedback": "小龙的故事很温暖"}).status_code == 200
    assert client.post(f"/works/{work_id}/review", headers=admin, json={"state": "approved", "featured": True}).status_code == 200
    assert client.get("/works/showcase", headers=student).json()["works"][0]["assetId"] == work_id
    assert client.put("/classrooms/class-a/teachers", headers=admin, json={"teacherIds": [teachers[1]]}).status_code == 200
    assert client.get("/classrooms/class-a/students", headers=teacher).status_code == 403
    assert client.get("/classrooms/class-a/students", headers=other_teacher).status_code == 200
    assert client.post(f"/works/{work_id}/comments", headers=teacher, json={"body": "权限已撤销"}).status_code == 403
    assert client.post(f"/works/{work_id}/comments", headers=other_teacher, json={"body": "接手后的老师点评"}).status_code == 200
