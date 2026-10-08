import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.agents.catalog import AgentCatalog, ManagedTool
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration
from apps.api.app.usage.service import UsageLedger


pytestmark = pytest.mark.integration


class FakeGateway:
    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        return TextGeneration("fake", "fake", "智能体完成了故事草稿。")


class RecordingGateway(FakeGateway):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        self.prompts.append(prompt)
        return super().generate_text(organization_id, prompt, allow_foreign=allow_foreign)


def test_agent_dispatch_executes_and_returns_structured_result() -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth, model_gateway=FakeGateway()))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/agents/dispatch", headers={"Authorization": f"Bearer {token}"}, json={"agentId": "writing-coach", "prompt": "写海洋故事"})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "智能体完成" in response.json()["content"]
    assert len(response.json()["teachingSteps"]) == 3


def test_agent_dispatch_applies_enabled_matching_skill_instruction() -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    catalog = AgentCatalog()
    catalog.save(ManagedTool("story-safety", "skill", "故事创作规则", "text", True, "org-001", "先给出三个适合小学三年级的故事主角。"))
    catalog.save(ManagedTool("disabled", "skill", "停用规则", "text", False, "org-001", "这句话不应该出现。"))
    catalog.save(ManagedTool("image-only", "skill", "绘画规则", "image", True, "org-001", "这句话也不应该出现。"))
    gateway = RecordingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway, agent_catalog=catalog))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/agents/dispatch", headers={"Authorization": f"Bearer {token}"}, json={"agentId": "writing-coach", "prompt": "写海洋故事"})

    assert response.status_code == 200
    assert "先给出三个适合小学三年级的故事主角。" in gateway.prompts[-1]
    assert "这句话不应该出现。" not in gateway.prompts[-1]


def test_admin_saved_skill_is_applied_to_student_agent_dispatch() -> None:
    auth = AuthService(users={
        "admin": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    gateway = RecordingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway, agent_catalog=AgentCatalog()))
    admin_token = client.post("/auth/login", json={"username": "admin", "password": "password"}).json()["accessToken"]
    student_token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    saved = client.post(
        "/agents/skills",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "toolId": "story-outline",
            "name": "故事创作步骤",
            "capabilities": "text, html",
            "enabled": True,
            "instruction": "先引导学生选角色、地点和目标，再给出三步创作提示。",
        },
    )
    response = client.post(
        "/agents/dispatch",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"agentId": "writing-coach", "prompt": "写一个海底探险故事"},
    )

    assert saved.status_code == 200
    assert saved.json()["instruction"] == "先引导学生选角色、地点和目标，再给出三步创作提示。"
    assert response.status_code == 200
    assert "先引导学生选角色、地点和目标，再给出三步创作提示。" in gateway.prompts[-1]


def test_student_cannot_bypass_closed_classroom_when_dispatching_agent() -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-3-1")})
    classrooms = AssistanceManager()
    classrooms.create("class-3-1", "org-001")
    client = TestClient(create_app(auth_service=auth, model_gateway=FakeGateway(), assistance_manager=classrooms))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/agents/dispatch", headers={"Authorization": f"Bearer {token}"}, json={"agentId": "writing-coach", "prompt": "写海洋故事", "classroomOpen": True, "featureEnabled": True})

    assert response.status_code == 423


def test_student_cannot_bypass_configured_text_quota_when_dispatching_agent() -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    usage = UsageLedger({("student", "student-001", "text"): 0})
    client = TestClient(create_app(auth_service=auth, model_gateway=FakeGateway(), usage_ledger=usage))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/agents/dispatch", headers={"Authorization": f"Bearer {token}"}, json={"agentId": "writing-coach", "prompt": "写海洋故事", "quotaAvailable": True})

    assert response.status_code == 429
