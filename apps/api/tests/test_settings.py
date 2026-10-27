from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.settings.service import OrganizationSettings, SettingsStore


def test_legacy_platform_name_is_displayed_as_current_brand(tmp_path) -> None:
    path = tmp_path / "settings.sqlite"
    store = SettingsStore(path)
    store.save(OrganizationSettings("org-001", display_name="AI 创造力学习工作台"))
    assert SettingsStore(path).get("org-001").display_name == "星芽 AI 创作岛"


def test_admin_can_save_and_read_organization_settings() -> None:
    auth = AuthService(users={"admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth, settings_store=SettingsStore()))
    login = client.post("/auth/admin/login", json={"username": "admin", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    saved = client.put("/settings", headers=headers, json={"displayName": "星芽小学", "studentHomeEnabled": False, "maintenanceMessage": "今晚维护"})
    loaded = client.get("/settings", headers=headers)

    assert saved.status_code == 200
    assert loaded.json() == {"displayName": "星芽小学", "studentHomeEnabled": False, "maintenanceMessage": "今晚维护", "showcaseColumns": 4, "showcaseRows": 2, "showcaseSort": "featured", "showcaseKind": "all", "videoDurationSeconds": 5}


def test_closed_student_hall_blocks_new_creative_requests_and_returns_maintenance_message() -> None:
    auth = AuthService(users={
        "admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    client = TestClient(create_app(auth_service=auth, settings_store=SettingsStore()))
    admin_login = client.post("/auth/admin/login", json={"username": "admin", "password": "password"})
    student_login = client.post("/auth/login", json={"username": "student", "password": "password"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}
    student_headers = {"Authorization": f"Bearer {student_login.json()['accessToken']}"}

    client.put("/settings", headers=admin_headers, json={"displayName": "星芽小学", "studentHomeEnabled": False, "maintenanceMessage": "晚上维护"})

    status = client.get("/settings/student-access", headers=student_headers)
    text_request = client.post("/models/text/generate", headers=student_headers, json={"prompt": "写一首小诗"})
    media_request = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "太空小猫"})

    assert status.json() == {"enabled": False, "displayName": "星芽小学", "maintenanceMessage": "晚上维护", "showcaseColumns": 4, "showcaseRows": 2, "showcaseSort": "featured", "showcaseKind": "all", "videoDurationSeconds": 5}
    assert text_request.status_code == 423
    assert media_request.status_code == 423
    assert text_request.json()["detail"] == "晚上维护"


def test_admin_controls_video_duration_and_student_cannot_override_it(tmp_path) -> None:
    from apps.api.app.media.jobs import MediaJobLedger

    auth = AuthService(users={
        "admin": UserRecord("admin-001", "org-001", "organization_admin", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    store = SettingsStore(tmp_path / "settings.sqlite")
    ledger = MediaJobLedger(tmp_path / "jobs.sqlite")
    client = TestClient(create_app(auth_service=auth, settings_store=store, media_ledger=ledger))
    admin = client.post("/auth/admin/login", json={"username": "admin", "password": "password"})
    student = client.post("/auth/login", json={"username": "student", "password": "password"})
    admin_headers = {"Authorization": f"Bearer {admin.json()['accessToken']}"}
    student_headers = {"Authorization": f"Bearer {student.json()['accessToken']}"}

    earlier = client.post("/media/jobs", headers=student_headers, json={"kind": "video", "prompt": "切换前"})
    saved = client.put("/settings", headers=admin_headers, json={"displayName": "星芽小学", "videoDurationSeconds": 10})
    rejected = client.post("/media/jobs", headers=student_headers, json={"kind": "video", "prompt": "星空", "videoDurationSeconds": 5})
    created = client.post("/media/jobs", headers=student_headers, json={"kind": "video", "prompt": "星空"})

    assert saved.status_code == 200
    assert saved.json()["videoDurationSeconds"] == 10
    assert rejected.status_code == 422
    assert created.status_code == 202
    assert ledger.get(earlier.json()["jobId"]).video_duration_seconds == 5
    assert client.get("/settings/student-access", headers=student_headers).json()["videoDurationSeconds"] == 10
    assert ledger.get(created.json()["jobId"]).video_duration_seconds == 10
    assert SettingsStore(tmp_path / "settings.sqlite").get("org-001").video_duration_seconds == 10

    unrelated_update = client.put("/settings", headers=admin_headers, json={"displayName": "新名称"})
    assert unrelated_update.json()["videoDurationSeconds"] == 10
    assert SettingsStore(tmp_path / "settings.sqlite").get("org-001").video_duration_seconds == 10
