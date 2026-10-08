from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.settings.service import SettingsStore


def test_admin_can_save_and_read_organization_settings() -> None:
    auth = AuthService(users={"admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth, settings_store=SettingsStore()))
    login = client.post("/auth/login", json={"username": "admin", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    saved = client.put("/settings", headers=headers, json={"displayName": "星芽小学", "studentHomeEnabled": False, "maintenanceMessage": "今晚维护"})
    loaded = client.get("/settings", headers=headers)

    assert saved.status_code == 200
    assert loaded.json() == {"displayName": "星芽小学", "studentHomeEnabled": False, "maintenanceMessage": "今晚维护", "showcaseColumns": 4, "showcaseRows": 2, "showcaseSort": "featured", "showcaseKind": "all"}


def test_closed_student_hall_blocks_new_creative_requests_and_returns_maintenance_message() -> None:
    auth = AuthService(users={
        "admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    client = TestClient(create_app(auth_service=auth, settings_store=SettingsStore()))
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "password"})
    student_login = client.post("/auth/login", json={"username": "student", "password": "password"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}
    student_headers = {"Authorization": f"Bearer {student_login.json()['accessToken']}"}

    client.put("/settings", headers=admin_headers, json={"displayName": "星芽小学", "studentHomeEnabled": False, "maintenanceMessage": "晚上维护"})

    status = client.get("/settings/student-access", headers=student_headers)
    text_request = client.post("/models/text/generate", headers=student_headers, json={"prompt": "写一首小诗"})
    media_request = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "太空小猫"})

    assert status.json() == {"enabled": False, "displayName": "星芽小学", "maintenanceMessage": "晚上维护", "showcaseColumns": 4, "showcaseRows": 2, "showcaseSort": "featured", "showcaseKind": "all"}
    assert text_request.status_code == 423
    assert media_request.status_code == 423
    assert text_request.json()["detail"] == "晚上维护"
