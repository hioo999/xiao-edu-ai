from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest

from apps.api.app.agents.catalog import AgentCatalog, ManagedTool
from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.knowledge.scopes import KnowledgeScope
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault
from apps.api.app.usage.service import UsageLedger


class Gateway:
    def __init__(self):
        self.prompts = []
        self.fail = False
        self.content = "月球上的花园开花了。"

    def generate_text(self, organization_id, prompt, **options):
        self.prompts.append(prompt)
        if self.fail:
            raise ValueError("test failure")
        return TextGeneration("text", "lightweight", self.content)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_ARTIFACT_STORAGE_PATH", str(tmp_path / "artifacts"))
    auth = AuthService({name: UserRecord(name, "school", "student", hash_password("password")) for name in ["first", "second"]})
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(ModelProvider("text", "school", ModelCapability.TEXT, "domestic", 1, "private-key", model_id="test-model"))
    registry.register(ModelProvider("image", "school", ModelCapability.IMAGE, "domestic", 1, "image-key"))
    catalog = AgentCatalog(tmp_path / "catalog.db")
    catalog.save(ManagedTool("story", "skill", "故事规则", "text", True, "school", "每次故事必须出现一朵花。"))
    knowledge = KnowledgeCatalog()
    public = knowledge.add(KnowledgeScope.ORGANIZATION, "school", "月球花园", "school", "月球花园有蓝色的花。")
    private = knowledge.add(KnowledgeScope.STUDENT, "second", "秘密", "school", "他人的私人内容")
    ledger = UsageLedger({("student", "first", "text"): 10, ("student", "first", "image"): 2})
    gateway = Gateway()
    def app():
        return create_app(auth, registry, model_gateway=gateway, agent_catalog=catalog, knowledge_catalog=knowledge, usage_ledger=ledger)
    client = TestClient(app())
    headers = {name: {"Authorization": f"Bearer {client.post('/auth/login', json={'username': name, 'password': 'password'}).json()['accessToken']}"} for name in ["first", "second"]}
    agent = client.post("/agents/mine", headers=headers["first"], json={"name": "故事精灵", "instructions": "直接写故事，不要反问。", "providerId": "text"}).json()["agentId"]
    return client, headers, agent, gateway, ledger, public, private, app


def test_sessions_restore_context_and_keep_other_students_out(workspace):
    client, headers, agent, gateway, ledger, public, private, app = workspace
    configuration = {"skillIds": ["story"], "knowledgeIds": [public.document_id]}
    assert client.put(f"/student-agents/{agent}/settings", headers=headers["first"], json=configuration).status_code == 200
    session = client.post(f"/student-agents/{agent}/sessions", headers=headers["first"]).json()["sessionId"]
    endpoint = f"/student-agents/sessions/{session}"
    reply = client.post(endpoint + "/messages", headers=headers["first"], json={"text": "写月球花园"})
    assert reply.status_code == 200, reply.text
    assert reply.json()["message"]["assetId"].startswith("asset-")
    assert "每次故事必须出现一朵花" in gateway.prompts[-1]
    assert "月球花园有蓝色的花" in gateway.prompts[-1]
    assert "他人的私人内容" not in gateway.prompts[-1]
    assert client.get(endpoint, headers=headers["second"]).status_code == 404
    assert client.put(f"/student-agents/{agent}/settings", headers=headers["first"], json={"knowledgeIds": [private.document_id]}).status_code == 422
    reopened = TestClient(app()).get(endpoint, headers=headers["first"])
    assert reopened.json()["messages"][1]["text"] == "月球上的花园开花了。"
    assert client.post(endpoint + "/messages", headers=headers["first"], json={"text": "继续写"}).status_code == 200
    assert "月球上的花园开花了" in gateway.prompts[-1]
    assert ledger.committed("student", "first", "text") == 2


def test_failed_generation_releases_points_and_does_not_append_fake_reply(workspace):
    client, headers, agent, gateway, ledger, *_ = workspace
    session = client.post(f"/student-agents/{agent}/sessions", headers=headers["first"]).json()["sessionId"]
    endpoint = f"/student-agents/sessions/{session}"
    gateway.fail = True
    assert client.post(endpoint + "/messages", headers=headers["first"], json={"text": "写故事"}).status_code == 502
    assert client.get(endpoint, headers=headers["first"]).json()["messages"] == []
    assert ledger.summary("student", "first")[1]["reserved"] == 0
    assert ledger.committed("student", "first", "text") == 0
    ledger.set_limit("student", "first", "text", 0)
    gateway.fail = False
    assert client.post(endpoint + "/messages", headers=headers["first"], json={"text": "写故事"}).status_code == 429


def test_html_and_image_agents_create_real_artifacts_and_queued_tasks(workspace):
    client, headers, agent, gateway, ledger, *_ = workspace
    session = client.post(f"/student-agents/{agent}/sessions", headers=headers["first"]).json()["sessionId"]
    endpoint = f"/student-agents/sessions/{session}/messages"
    gateway.content = '<!doctype html><html><body><button onclick="this.textContent=1">开始</button></body></html>'
    client.put(f"/student-agents/{agent}/settings", headers=headers["first"], json={"capability": "html"})
    response = client.post(endpoint, headers=headers["first"], json={"text": "做小游戏"})
    assert response.status_code == 200, response.text
    result = response.json()["message"]
    assert "onclick" in result["html"]
    assert "Content-Security-Policy" in result["html"]
    assert client.get(f"/works/{result['assetId']}/download", headers=headers["first"]).status_code == 200
    client.put(f"/student-agents/{agent}/settings", headers=headers["first"], json={"capability": "image"})
    gateway.content = "一座月球花园城堡"
    result = client.post(endpoint, headers=headers["first"], json={"text": "画出来"}).json()["message"]
    job = client.get(f"/media/jobs/{result['jobId']}", headers=headers["first"])
    assert job.status_code == 200
    assert job.json()["kind"] == "image"
    assert ledger.summary("student", "first")[0]["reserved"] == 1
