from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


def test_authenticated_user_can_read_current_session_identity() -> None:
    service = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    client = TestClient(create_app(service))
    login = client.post("/auth/login", json={"username": "student", "password": "password"})

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})

    assert response.json() == {"userId": "student-001", "organizationId": "org-001", "role": "student", "classId": None}
