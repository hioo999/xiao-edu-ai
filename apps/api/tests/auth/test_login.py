from datetime import datetime, timedelta, timezone

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from fastapi.testclient import TestClient

from apps.api.app.auth.routes import create_auth_router
from apps.api.app.main import create_app


def test_login_returns_user_role_and_organization() -> None:
    service = AuthService(
        users={
            "student-001": UserRecord(
                user_id="student-001",
                organization_id="org-001",
                role="student",
                password_hash=hash_password("class-password"),
            )
        }
    )

    session = service.login("student-001", "class-password")

    assert session.user_id == "student-001"
    assert session.organization_id == "org-001"
    assert session.role == "student"


def test_login_route_returns_session_context() -> None:
    service = AuthService(
        users={
            "student-001": UserRecord(
                user_id="student-001",
                organization_id="org-001",
                role="student",
                password_hash=hash_password("class-password"),
            )
        }
    )
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(create_auth_router(service), prefix="/auth")

    response = TestClient(app).post(
        "/auth/login",
        json={"username": "student-001", "password": "class-password"},
    )

    assert response.status_code == 200
    assert response.json()["organizationId"] == "org-001"


def test_default_access_session_lasts_one_day() -> None:
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("class-password"))})
    before = datetime.now(timezone.utc)

    _, expires_at = service.create_access_session(service.login("student-001", "class-password"))

    assert timedelta(hours=23, minutes=59) <= expires_at - before <= timedelta(days=1, seconds=1)


def test_login_route_rejects_invalid_password() -> None:
    service = AuthService(
        users={
            "student-001": UserRecord(
                user_id="student-001",
                organization_id="org-001",
                role="student",
                password_hash=hash_password("class-password"),
            )
        }
    )
    app = create_app(service)

    response = TestClient(app).post(
        "/auth/login",
        json={"username": "student-001", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_public_and_admin_login_accept_only_their_own_roles() -> None:
    service = AuthService(users={
        "learner": UserRecord("learner", "org-001", "student", hash_password("student-pass")),
        "teacher": UserRecord("teacher", "org-001", "teacher", hash_password("teacher-pass")),
        "parent": UserRecord("parent", "org-001", "parent", hash_password("parent-pass")),
        "operator": UserRecord("operator", "org-001", "platform_admin", hash_password("admin-pass")),
    })
    client = TestClient(create_app(service))
    for username, password in (("learner", "student-pass"), ("teacher", "teacher-pass"), ("parent", "parent-pass")):
        assert client.post("/auth/login", json={"username": username, "password": password}).status_code == 200
        assert client.post("/auth/admin/login", json={"username": username, "password": password}).status_code == 401
    assert client.post("/auth/login", json={"username": "operator", "password": "admin-pass"}).status_code == 401
    admin = client.post("/auth/admin/login", json={"username": "operator", "password": "admin-pass"})
    assert admin.status_code == 200
    assert admin.json()["role"] == "platform_admin"


def test_bootstrap_admin_creates_only_the_first_platform_admin() -> None:
    service = AuthService(users={})
    client = TestClient(create_app(service))
    request = {"username": "platform-admin", "password": "secure-password", "organizationId": "org-001"}

    created = client.post("/auth/bootstrap-admin", json=request)
    repeated = client.post("/auth/bootstrap-admin", json=request)

    assert created.status_code == 200
    assert created.json()["role"] == "platform_admin"
    assert repeated.status_code == 409


def test_protected_route_requires_bearer_token() -> None:
    service = AuthService(users={})
    app = create_app(service)

    response = TestClient(app).get("/organizations/org-001")

    assert response.status_code == 401


def test_sqlite_persists_hashed_access_session_across_api_restart(tmp_path) -> None:
    database_path = tmp_path / "platform.db"
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("class-password"))}, storage_path=database_path)
    token, _ = service.create_access_session(service.login("student-001", "class-password"))

    restarted_service = AuthService(users={}, storage_path=database_path)

    assert restarted_service.resolve_access_session(token).user_id == "student-001"
    import sqlite3
    with sqlite3.connect(database_path) as connection:
        stored_token = connection.execute("select token_hash from access_sessions").fetchone()[0]
    assert stored_token != token


def test_disabling_student_revokes_existing_access_session() -> None:
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("class-password"))})
    token, _ = service.create_access_session(service.login("student-001", "class-password"))

    service.set_enabled("student-001", "org-001", False)

    import pytest
    with pytest.raises(PermissionError):
        service.resolve_access_session(token)


def test_expired_student_cannot_login_or_use_existing_session() -> None:
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("class-password"))})
    token, _ = service.create_access_session(service.login("student-001", "class-password"))
    service.set_expiry("student-001", "org-001", datetime.now(timezone.utc) - timedelta(minutes=1))

    import pytest
    with pytest.raises(PermissionError):
        service.login("student-001", "class-password")
    with pytest.raises(PermissionError):
        service.resolve_access_session(token)


def test_sqlite_persists_student_expiration(tmp_path) -> None:
    database_path = tmp_path / "platform.db"
    service = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("class-password"))}, storage_path=database_path)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    service.set_expiry("student-001", "org-001", expires_at)

    restarted_service = AuthService(users={}, storage_path=database_path)

    assert restarted_service.users_for_organization("org-001", role="student")[0][1].expires_at == expires_at


def test_batch_provisioning_applies_shared_expiration() -> None:
    service = AuthService(users={})
    expires_at = datetime.now(timezone.utc) + timedelta(hours=4)

    service.provision_students(prefix="class3", count=2, class_id="class-a", initial_password="welcome-123", organization_id="org-001", expires_at=expires_at)

    assert [user.expires_at for _, user in service.users_for_organization("org-001", role="student")] == [expires_at, expires_at]


def test_batch_provisioning_persists_class_id_across_restart(tmp_path) -> None:
    database_path = tmp_path / "platform.db"
    service = AuthService(users={}, storage_path=database_path)
    service.provision_students(
        prefix="class3",
        count=2,
        class_id="class-a",
        initial_password="welcome-123",
        organization_id="org-001",
    )

    restarted_service = AuthService(users={}, storage_path=database_path)

    assert [user.class_id for _, user in restarted_service.users_for_organization("org-001", role="student")] == ["class-a", "class-a"]


def test_student_listing_filters_by_class_search_state_and_expiry() -> None:
    now = datetime.now(timezone.utc)
    service = AuthService(users={
        "class-a-001": UserRecord("student-a", "org-001", "student", hash_password("password"), True, now + timedelta(hours=1), "class-a"),
        "class-a-002": UserRecord("student-b", "org-001", "student", hash_password("password"), False, now + timedelta(hours=1), "class-a"),
        "class-b-001": UserRecord("student-c", "org-001", "student", hash_password("password"), True, now - timedelta(hours=1), "class-b"),
    })

    filtered = service.users_for_organization("org-001", role="student", class_id="class-a", enabled=True, search="001")
    expired = service.users_for_organization("org-001", role="student", expired=True)

    assert [username for username, _ in filtered] == ["class-a-001"]
    assert [username for username, _ in expired] == ["class-b-001"]


def test_revoke_organization_sessions_keeps_requesting_admin_session() -> None:
    service = AuthService(users={
        "admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    admin_token, _ = service.create_access_session(service.login("admin", "password"))
    student_token, _ = service.create_access_session(service.login("student", "password"))

    revoked = service.revoke_organization_sessions("org-001", except_user_id="admin-001")

    assert revoked == 1
    assert service.resolve_access_session(admin_token).user_id == "admin-001"
    import pytest
    with pytest.raises(PermissionError):
        service.resolve_access_session(student_token)


def test_teacher_can_batch_provision_students_in_own_organization() -> None:
    from apps.api.app.classrooms.assistance import AssistanceManager

    service = AuthService(
        users={
            "teacher-001": UserRecord(
                user_id="teacher-001",
                organization_id="org-001",
                role="teacher",
                password_hash=hash_password("teacher-password"),
            )
        }
    )
    classrooms = AssistanceManager()
    classrooms.create("class-a", "org-001").teachers = {"teacher-001"}
    client = TestClient(create_app(service, assistance_manager=classrooms))
    login = client.post(
        "/auth/login",
        json={"username": "teacher-001", "password": "teacher-password"},
    )

    response = client.post(
        "/organizations/org-001/students/batch",
        headers={"Authorization": f"Bearer {login.json()['accessToken']}"},
        json={
            "prefix": "class3",
            "count": 2,
            "classId": "class-a",
            "initialPassword": "welcome-123",
        },
    )

    assert response.status_code == 200
    assert [student["username"] for student in response.json()["students"]] == [
        "class3-001",
        "class3-002",
    ]


def test_organization_admin_can_create_staff_and_bulk_disable_accounts() -> None:
    service = AuthService(users={"admin": UserRecord("admin-001", "org-001", "organization_admin", hash_password("password"))})
    client = TestClient(create_app(service))
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    created = client.post("/organizations/org-001/staff", headers=headers, json={"username": "teacher-001", "password": "teacher-password", "role": "teacher"})
    bulk = client.post("/organizations/org-001/accounts/bulk-state", headers=headers, json={"usernames": ["teacher-001"], "enabled": False})
    listed = client.get("/organizations/org-001/staff", headers=headers)

    assert created.status_code == 200
    assert bulk.json() == {"changed": 1}
    teacher = next(item for item in listed.json()["staff"] if item["username"] == "teacher-001")
    assert teacher["enabled"] is False


def test_teacher_cannot_create_staff_accounts() -> None:
    service = AuthService(users={"teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password"))})
    client = TestClient(create_app(service))
    login = client.post("/auth/login", json={"username": "teacher", "password": "password"})

    response = client.post(
        "/organizations/org-001/staff",
        headers={"Authorization": f"Bearer {login.json()['accessToken']}"},
        json={"username": "teacher-002", "password": "teacher-password", "role": "teacher"},
    )

    assert response.status_code == 403
