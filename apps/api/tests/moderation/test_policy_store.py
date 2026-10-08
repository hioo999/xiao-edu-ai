from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.moderation.service import ModerationPolicyStore, ModerationService


def test_policy_store_round_trips_blocked_terms(tmp_path) -> None:
    store = ModerationPolicyStore(tmp_path / "platform.db")
    store.save(ModerationService().update_policy(enabled=False, blocked_terms=[" 危险词 ", "辱骂词", "危险词"]))

    policy = store.get()

    assert policy.enabled is False
    assert policy.blocked_terms == ("危险词", "辱骂词")


def test_admin_can_update_and_read_moderation_policy() -> None:
    auth = AuthService(users={"admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth, moderation_service=ModerationService(blocked_terms={"旧词"})))
    login = client.post("/auth/login", json={"username": "admin", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    updated = client.put("/moderation/policy", headers=headers, json={"enabled": True, "blockedTerms": ["危险词", "辱骂词"]})
    loaded = client.get("/moderation/policy", headers=headers)

    assert updated.status_code == 200
    assert loaded.json()["blockedTerms"] == ["危险词", "辱骂词"]
    assert loaded.json()["status"] == "active"


def test_disabled_policy_allows_blocked_content() -> None:
    service = ModerationService(blocked_terms={"危险词"})
    service.update_policy(enabled=False, blocked_terms=["危险词"])

    assert service.check("这是危险词", mode="classroom") == "allowed"
