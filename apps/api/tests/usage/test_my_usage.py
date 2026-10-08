from fastapi.testclient import TestClient

from apps.api.app.main import create_app


def test_student_reads_only_its_effective_creation_credits(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_DB_PATH", str(tmp_path / "platform.sqlite"))
    client = TestClient(create_app())
    admin = client.post("/auth/bootstrap-admin", json={"username": "usage-admin", "password": "password123", "organizationId": "usage-org"}).json()
    token = {"Authorization": f"Bearer {admin['accessToken']}"}
    client.post("/organizations/usage-org/students/batch", headers=token, json={"prefix": "u", "count": 1, "classId": "c1", "initialPassword": "password123"})
    client.post("/usage/limits", headers=token, json={"scope": "student", "scopeId": "u-001", "metric": "image", "limit": 3})
    student = client.post("/auth/login", json={"username": "u-001", "password": "password123"}).json()
    result = client.get("/usage/mine", headers={"Authorization": f"Bearer {student['accessToken']}"})
    assert result.status_code == 200
    assert result.json()["metrics"] == [{"metric": "image", "limit": 3, "used": 0, "reserved": 0, "scope": "student", "scopeId": "u-001", "remaining": 3}]
