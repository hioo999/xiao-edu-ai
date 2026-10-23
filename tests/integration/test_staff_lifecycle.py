import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.courses.catalog import CourseCatalog, CourseRecord
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


@pytest.fixture
def staff_platform(tmp_path, monkeypatch):
    database = tmp_path / "platform.db"
    monkeypatch.setenv("PLATFORM_DB_PATH", str(database))
    for variable in ("WORK_ARTIFACT_STORAGE_PATH", "WORK_INTERACTION_STORAGE_PATH", "SHOWCASE_MEDIA_STORAGE_PATH", "LEARNING_STORAGE_PATH", "DEPLOYMENT_STORAGE_PATH"):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))
    password_hash = hash_password("password123")
    auth = AuthService({
        "admin": UserRecord("admin", "school", "organization_admin", password_hash),
        "platform": UserRecord("platform", "school", "platform_admin", password_hash),
        "source": UserRecord("source", "school", "teacher", password_hash),
        "replacement": UserRecord("replacement", "school", "teacher", password_hash),
        "foreign": UserRecord("foreign", "other-school", "teacher", password_hash),
        "student": UserRecord("student", "school", "student", password_hash, class_id="class-a"),
    }, storage_path=database)
    classrooms = AssistanceManager(database)
    classrooms.create("class-a", "school").teachers = {"source"}
    classrooms.assign_teachers("class-a", {"source"})
    classrooms.open("class-a")
    classrooms.grant_assistance("class-a", teacher_id="source", student_id="student")
    courses = CourseCatalog(database)
    courses.save(CourseRecord("course-a", "school", "source", "魔法故事课", ""))
    courses.publish_to_class("course-a", "class-a", "school")
    client = TestClient(create_app(auth_service=auth, assistance_manager=classrooms, course_catalog=courses), raise_server_exceptions=False)
    headers = {}
    for username in ("admin", "source", "replacement", "student"):
        response = client.post("/auth/login", json={"username": username, "password": "password123"})
        headers[username] = {"Authorization": f"Bearer {response.json()['accessToken']}"}
    return client, headers, auth, classrooms, courses, database


def test_staff_password_reset_revokes_sessions_and_assistance(staff_platform):
    client, headers, _, classrooms, _, _ = staff_platform
    response = client.post("/organizations/school/staff/source/reset-password", headers=headers["admin"], json={"password": "new-password123"})
    assert response.status_code == 200
    assert client.get("/auth/me", headers=headers["source"]).status_code == 401
    assert client.post("/auth/login", json={"username": "source", "password": "new-password123"}).status_code == 200
    assert not classrooms.can_act_as("class-a", "source", "student")


def test_teacher_with_teaching_resources_cannot_be_disabled_without_handover(staff_platform):
    client, headers, _, _, _, _ = staff_platform
    response = client.put("/organizations/school/staff/source/state", headers=headers["admin"], json={"enabled": False})
    assert response.status_code == 409
    assert client.get("/auth/me", headers=headers["source"]).status_code == 200
    assert client.post("/organizations/school/accounts/bulk-state", headers=headers["admin"], json={"usernames": ["replacement", "source"], "enabled": False}).status_code == 409
    assert client.get("/auth/me", headers=headers["replacement"]).status_code == 200


def test_teacher_handover_transfers_classes_courses_and_revokes_source(staff_platform):
    client, headers, _, classrooms, _, database = staff_platform
    plan = client.get("/organizations/school/staff/source/handover-plan", headers=headers["admin"])
    assert plan.status_code == 200
    assert plan.json()["classIds"] == ["class-a"]
    assert plan.json()["courseIds"] == ["course-a"]
    response = client.post("/organizations/school/staff/source/handover", headers=headers["admin"], json={"replacementUserId": "replacement", "reason": "教师离职交接"})
    assert response.status_code == 200
    assert response.json()["sourceDisabled"] is True
    assert client.get("/auth/me", headers=headers["source"]).status_code == 401
    assert client.get("/classrooms/class-a", headers=headers["replacement"]).status_code == 200
    assert client.post("/courses", headers=headers["replacement"], json={"courseId": "course-a", "title": "接任老师更新"}).status_code == 200
    assert not classrooms.can_act_as("class-a", "source", "student")
    assert AuthService({}, storage_path=database).user_for_id("source").enabled is False
    assert AssistanceManager(database).classrooms["class-a"].teachers == {"replacement"}
    assert CourseCatalog(database).get("course-a", "school").author_user_id == "replacement"
    history = client.get("/organizations/school/staff/source/handover-history", headers=headers["admin"]).json()["handovers"]
    assert len(history) == 1
    assert history[0]["reason"] == "教师离职交接"


@pytest.mark.parametrize("table,operation", [("courses", "update of author_user_id"), ("audit_records", "insert")])
def test_handover_database_failure_rolls_back_every_resource(staff_platform, table, operation):
    client, headers, _, _, _, database = staff_platform
    with sqlite3.connect(database) as connection:
        connection.execute(f"create trigger fail_handover before {operation} on {table} begin select raise(abort, 'injected failure'); end")
    response = client.post("/organizations/school/staff/source/handover", headers=headers["admin"], json={"replacementUserId": "replacement", "reason": "验证失败回滚"})
    assert response.status_code == 503
    assert client.get("/auth/me", headers=headers["source"]).status_code == 200
    assert client.get("/classrooms/class-a", headers=headers["source"]).status_code == 200
    assert client.get("/classrooms/class-a", headers=headers["replacement"]).status_code == 403
    assert CourseCatalog(database).get("course-a", "school").author_user_id == "source"
    assert client.get("/organizations/school/staff/source/handover-history", headers=headers["admin"]).json()["handovers"] == []


@pytest.mark.parametrize("replacement", ["source", "foreign", "student", "missing"])
def test_handover_rejects_invalid_replacement(staff_platform, replacement):
    client, headers, _, _, _, _ = staff_platform
    response = client.post("/organizations/school/staff/source/handover", headers=headers["admin"], json={"replacementUserId": replacement, "reason": "交接验证"})
    assert response.status_code == 422
    assert client.get("/auth/me", headers=headers["source"]).status_code == 200


def test_legacy_account_routes_cannot_bypass_staff_protections(staff_platform):
    client, headers, _, _, _, _ = staff_platform
    assert client.post("/organizations/school/students/source/state", headers=headers["admin"], json={"enabled": False}).status_code == 404
    assert client.post("/organizations/school/students/platform/reset-password", headers=headers["admin"], json={"password": "hijacked-password"}).status_code == 404
    assert client.post("/organizations/school/accounts/bulk-state", headers=headers["admin"], json={"usernames": ["platform"], "enabled": False}).status_code == 403
    assert client.put("/organizations/school/staff/admin/state", headers=headers["admin"], json={"enabled": False}).status_code == 409


def test_staff_expiry_uses_shanghai_time_and_force_logout_is_immediate(staff_platform):
    client, headers, auth, _, _, _ = staff_platform
    expires = client.put("/organizations/school/staff/replacement/expiry", headers=headers["admin"], json={"expiresAt": "2099-01-01T18:00:00"})
    assert expires.status_code == 200
    assert auth.user_for_id("replacement").expires_at == datetime(2099, 1, 1, 10, tzinfo=timezone.utc)
    assert client.post("/organizations/school/staff/replacement/revoke-sessions", headers=headers["admin"]).status_code == 200
    assert client.get("/auth/me", headers=headers["replacement"]).status_code == 401


def test_non_admin_cannot_manage_staff_and_cross_school_is_rejected(staff_platform):
    client, headers, _, _, _, _ = staff_platform
    assert client.get("/organizations/school/staff/source/handover-plan", headers=headers["source"]).status_code == 403
    assert client.post("/organizations/other-school/staff/foreign/revoke-sessions", headers=headers["admin"]).status_code == 403


def test_disabled_teacher_cannot_be_reassigned_to_a_class(staff_platform):
    client, headers, _, _, _, _ = staff_platform
    assert client.put("/organizations/school/staff/replacement/state", headers=headers["admin"], json={"enabled": False}).status_code == 200
    response = client.put("/classrooms/class-a/teachers", headers=headers["admin"], json={"teacherIds": ["replacement"]})
    assert response.status_code == 422


def test_batch_student_expiry_uses_the_same_local_time_rule(staff_platform):
    client, headers, auth, _, _, _ = staff_platform
    response = client.post("/organizations/school/students/batch", headers=headers["admin"], json={"prefix": "local", "count": 1, "classId": "class-a", "initialPassword": "password123", "expiresAt": "2099-01-01T18:00:00"})
    assert response.status_code == 200
    assert auth.user_for_id("local-001").expires_at == datetime(2099, 1, 1, 10, tzinfo=timezone.utc)


def test_failed_session_revocation_does_not_partially_reset_a_password(staff_platform):
    client, headers, _, classrooms, _, database = staff_platform
    with sqlite3.connect(database) as connection:
        connection.execute("create trigger fail_session_revoke before delete on access_sessions begin select raise(abort, 'injected failure'); end")
    response = client.post("/organizations/school/staff/source/reset-password", headers=headers["admin"], json={"password": "new-password123"})
    assert response.status_code == 503
    assert client.post("/auth/login", json={"username": "source", "password": "password123"}).status_code == 200
    assert client.post("/auth/login", json={"username": "source", "password": "new-password123"}).status_code == 401
    assert client.get("/auth/me", headers=headers["source"]).status_code == 200
    assert classrooms.can_act_as("class-a", "source", "student")


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/courses", {"courseId": "late-course", "title": "不能在交接后留下新课程"}),
    ("POST", "/classrooms", {"classId": "late-class"}),
    ("DELETE", "/courses/course-a", None),
    ("POST", "/courses/course-a/unpublish", {"classId": "class-a"}),
])
def test_handover_rejects_a_stale_authenticated_course_write(staff_platform, monkeypatch, method, path, body):
    client, headers, auth, _, _, database = staff_platform
    accepted, resume = Event(), Event()
    resolve = auth.resolve_access_session
    source_token = headers["source"]["Authorization"].removeprefix("Bearer ")

    def delayed_session(token):
        session = resolve(token)
        if token == source_token:
            accepted.set()
            assert resume.wait(10)
        return session

    monkeypatch.setattr(auth, "resolve_access_session", delayed_session)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.request, method, path, headers=headers["source"], json=body)
        try:
            assert accepted.wait(10)
            assert client.post("/organizations/school/staff/source/handover", headers=headers["admin"], json={"replacementUserId": "replacement", "reason": "并发交接"}).status_code == 200
        finally:
            resume.set()
        assert pending.result(timeout=10).status_code == 403
    with pytest.raises(KeyError):
        CourseCatalog(database).get("late-course", "school")
    assert CourseCatalog(database).get("course-a", "school").author_user_id == "replacement"
    assert "late-class" not in AssistanceManager(database).classrooms
    assert [course.course_id for course in CourseCatalog(database).list_for_class("class-a", "school")] == ["course-a"]
