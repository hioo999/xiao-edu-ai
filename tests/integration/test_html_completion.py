from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.usage.service import UsageLedger


class RevisionModel:
    def __init__(self):
        self.prompts = []
        self.failed = False

    def generate_text(self, organization_id, prompt):
        self.prompts.append(prompt)
        if self.failed:
            raise ValueError("test provider failed")
        return TextGeneration("test", "tiny", '<html><body style="background:pink"><button onclick="this.textContent=1">探索</button></body></html>')


def test_web_revisions_charge_success_only_and_publish_playable_share(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_ARTIFACT_STORAGE_PATH", str(tmp_path / "artifacts"))
    auth = AuthService({"student": UserRecord("student", "school", "student", hash_password("password"))})
    gateway = RevisionModel()
    ledger = UsageLedger({("student", "student", "text"): 3})
    assets = CreativeAssetCatalog()
    client = TestClient(create_app(auth, model_gateway=gateway, usage_ledger=ledger, creative_asset_catalog=assets))
    headers = {"Authorization": "Bearer " + client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]}
    endpoint = "/projects/web-student/html"
    first = client.post(endpoint + "/generate", headers=headers, json={"prompt": "做小游戏"})
    assert first.status_code == 200, first.text
    assert "onclick" in first.json()["currentVersion"]["html"]
    assert client.post(endpoint + "/generate", headers=headers, json={"prompt": "把背景改蓝色"}).status_code == 200
    assert "background:pink" in gateway.prompts[-1]
    assert "把背景改蓝色" in gateway.prompts[-1]
    assert client.get(endpoint + "/versions/web-student-v1", headers=headers).status_code == 200
    assert ledger.committed("student", "student", "text") == 2
    gateway.failed = True
    assert client.post(endpoint + "/generate", headers=headers, json={"prompt": "失败测试"}).status_code == 502
    assert ledger.committed("student", "student", "text") == 2
    assert ledger.summary("student", "student")[0]["reserved"] == 0
    asset_id = first.json()["assetId"]
    assets.review(asset_id, "school", "approved", False)
    token = client.post("/shares", headers=headers, json={"assetId": asset_id}).json()["token"]
    shared = client.get("/shares/public/" + token)
    assert "onclick" in shared.json()["work"]["content"]
    assert "Content-Security-Policy" in shared.json()["work"]["content"]
