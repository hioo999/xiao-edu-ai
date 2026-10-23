from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration


class FakeGateway:
    last_prompt = ""

    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        assert organization_id == "org-001"
        assert "小兔" in prompt
        self.last_prompt = prompt
        return TextGeneration("text-primary", "demo-model", "一只在月球花园探险的小兔子，儿童绘本风格。")


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_student_can_polish_a_prompt_with_the_default_image_policy() -> None:
    auth = AuthService({"student": UserRecord("student-1", "org-001", "student", hash_password("pw"))})
    client = TestClient(create_app(auth_service=auth, model_gateway=FakeGateway()))

    response = client.post("/prompt-polish", headers=_login(client, "student", "pw"), json={"capability": "image", "content": "小兔在月球"})

    assert response.status_code == 200
    assert response.json()["content"].startswith("一只在月球")


def test_prompt_polishing_guardrail_forbids_follow_up_questions() -> None:
    auth = AuthService({"student": UserRecord("student-1", "org-001", "student", hash_password("pw"))})
    gateway = FakeGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway))

    response = client.post("/prompt-polish", headers=_login(client, "student", "pw"), json={"capability": "image", "content": "小兔在月球"})

    assert response.status_code == 200
    assert "禁止向学生提问" in gateway.last_prompt
    assert "如果学生只写了主题或关键词，也要主动补全" in gateway.last_prompt
    assert "只输出润色后的最终内容" in gateway.last_prompt


def test_admin_can_edit_a_policy_and_students_use_the_saved_template() -> None:
    auth = AuthService({
        "admin": UserRecord("admin-1", "org-001", "platform_admin", hash_password("pw")),
        "student": UserRecord("student-1", "org-001", "student", hash_password("pw")),
    })
    client = TestClient(create_app(auth_service=auth, model_gateway=FakeGateway()))

    saved = client.put("/prompt-polish/policies/image", headers=_login(client, "admin", "pw"), json={"instruction": "请将这句话改成儿童绘本画面：{input}", "enabled": True})
    policies = client.get("/prompt-polish/policies", headers=_login(client, "admin", "pw"))

    assert saved.status_code == 200
    assert next(item for item in policies.json()["policies"] if item["capability"] == "image")["instruction"].startswith("请将")


def test_admin_can_restore_the_default_polish_policy() -> None:
    auth = AuthService({
        "admin": UserRecord("admin-1", "org-001", "platform_admin", hash_password("pw")),
    })
    client = TestClient(create_app(auth_service=auth, model_gateway=FakeGateway()))
    headers = _login(client, "admin", "pw")
    client.put("/prompt-polish/policies/image", headers=headers, json={"instruction": "旧策略：{input}", "enabled": False})

    restored = client.post("/prompt-polish/policies/image/reset", headers=headers)
    policies = client.get("/prompt-polish/policies", headers=headers)
    image_policy = next(item for item in policies.json()["policies"] if item["capability"] == "image")

    assert restored.status_code == 200
    assert restored.json()["enabled"] is True
    assert image_policy["enabled"] is True
    assert image_policy["instruction"].startswith("你是小学 3-6 年级 AI 绘画课")
