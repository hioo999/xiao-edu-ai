import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.knowledge.scopes import KnowledgeScope
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration


pytestmark = pytest.mark.integration


class CapturingGateway:
    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        self.prompt = prompt
        return TextGeneration("fake", "fake", "完成")


def test_text_generation_includes_matching_organization_knowledge(tmp_path) -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    knowledge = KnowledgeCatalog(tmp_path / "knowledge.db")
    knowledge.add(KnowledgeScope.ORGANIZATION, "org-001", "网页提示", "org-001", "海洋页面使用蓝色。")
    gateway = CapturingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway, knowledge_catalog=knowledge))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/models/text/generate", headers={"Authorization": f"Bearer {token}"}, json={"prompt": "做一个海洋网页"})

    assert response.status_code == 200
    assert "网页提示" in gateway.prompt
    assert "海洋页面使用蓝色" in gateway.prompt
