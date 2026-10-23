from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.main import create_app


def test_teacher_can_open_classroom_and_grant_assistance() -> None:
    manager = AssistanceManager()
    classroom = manager.create("class-001", "org-001")
    classroom.teachers = {"teacher-001"}
    auth = AuthService(users={
        "teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student-001": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-001"),
    })
    client = TestClient(create_app(auth_service=auth, assistance_manager=manager))
    login = client.post("/auth/login", json={"username": "teacher-001", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    opened = client.post("/classrooms/class-001/open", headers=headers)
    granted = client.post("/classrooms/class-001/assistance", headers=headers, json={"studentId": "student-001"})
    dashboard = client.get("/classrooms/class-001", headers=headers)

    assert opened.json()["state"] == "open"
    assert granted.json()["studentId"] == "student-001"
    assert dashboard.json()["state"] == "open"


def test_granted_teacher_can_open_student_view_snapshot() -> None:
    manager = AssistanceManager()
    classroom = manager.create("class-001", "org-001")
    classroom.teachers = {"teacher-001"}
    auth = AuthService(users={
        "teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student-001": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-001"),
    })
    client = TestClient(create_app(auth_service=auth, assistance_manager=manager))
    login = client.post("/auth/login", json={"username": "teacher-001", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    client.post("/classrooms/class-001/open", headers=headers)
    client.post("/classrooms/class-001/assistance", headers=headers, json={"studentId": "student-001"})
    manager.report_presence("class-001", "student-001", active_feature="html", task_state="working", lesson_step=2, help_needed=True)

    response = client.get("/classrooms/class-001/students/student-001/view", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "classId": "class-001",
        "studentId": "student-001",
        "mode": "assisted_view",
        "readOnly": False,
        "activeFeature": "html",
        "taskState": "working",
        "lessonStep": 2,
        "helpNeeded": True,
    }


def test_teacher_only_lists_assigned_classrooms() -> None:
    manager = AssistanceManager()
    first = manager.create("class-001", "org-001")
    first.teachers = {"teacher-001"}
    second = manager.create("class-002", "org-001")
    second.teachers = {"teacher-002"}
    auth = AuthService(users={"teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth, assistance_manager=manager))
    login = client.post("/auth/login", json={"username": "teacher-001", "password": "password"})

    response = client.get("/classrooms", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})

    assert response.json()["classrooms"] == [{"classId": "class-001", "state": "paused", "teacherCount": 1, "onlineStudents": 0, "helpNeeded": 0}]


def test_admin_can_end_classroom_and_assign_teachers() -> None:
    manager = AssistanceManager()
    manager.create("class-001", "org-001")
    auth = AuthService(users={
        "admin": UserRecord("admin-001", "org-001", "organization_admin", hash_password("password")),
        "teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "teacher-002": UserRecord("teacher-002", "org-001", "teacher", hash_password("password")),
    })
    client = TestClient(create_app(auth_service=auth, assistance_manager=manager))
    login = client.post("/auth/login", json={"username": "admin", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    assigned = client.put("/classrooms/class-001/teachers", headers=headers, json={"teacherIds": ["teacher-001", "teacher-002"]})
    closed = client.post("/classrooms/class-001/close", headers=headers)

    assert assigned.json()["teacherIds"] == ["teacher-001", "teacher-002"]
    assert closed.json() == {"classId": "class-001", "state": "closed"}
