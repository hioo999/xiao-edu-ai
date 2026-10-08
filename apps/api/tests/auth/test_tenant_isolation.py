import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


def test_user_cannot_access_another_organization() -> None:
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

    with pytest.raises(PermissionError):
        service.require_organization(session, "org-002")


def test_student_cannot_access_another_organization_route() -> None:
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
    client = TestClient(create_app(service))
    login = client.post(
        "/auth/login",
        json={"username": "student-001", "password": "class-password"},
    )

    response = client.get(
        "/organizations/org-002",
        headers={"Authorization": f"Bearer {login.json()['accessToken']}"},
    )

    assert response.status_code == 403


def test_only_organization_admin_can_view_organization() -> None:
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
    client = TestClient(create_app(service))
    login = client.post(
        "/auth/login",
        json={"username": "teacher-001", "password": "teacher-password"},
    )

    response = client.get(
        "/organizations/org-001",
        headers={"Authorization": f"Bearer {login.json()['accessToken']}"},
    )

    assert response.status_code == 403
