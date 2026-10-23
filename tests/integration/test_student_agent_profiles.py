from fastapi.testclient import TestClient

from apps.api.app.agents.catalog import AgentCatalog
from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


def test_student_profiles_are_private_and_survive_catalog_restart(tmp_path):
    path = tmp_path / "agents.sqlite"
    auth = AuthService(users={
        "first": UserRecord("first", "school", "student", hash_password("password")),
        "second": UserRecord("second", "school", "student", hash_password("password")),
    })
    client = TestClient(create_app(auth, agent_catalog=AgentCatalog(path)))
    first = {"Authorization": f"Bearer {client.post('/auth/login', json={'username': 'first', 'password': 'password'}).json()['accessToken']}"}
    second = {"Authorization": f"Bearer {client.post('/auth/login', json={'username': 'second', 'password': 'password'}).json()['accessToken']}"}
    payload = {"name": "故事精灵", "description": "写童话", "category": "故事", "instructions": "先给故事，再给建议", "providerId": "deepseek-class"}

    created = client.post("/agents/mine", headers=first, json=payload)
    assert created.status_code == 200
    agent_id = created.json()["agentId"]
    assert client.get("/agents/mine", headers=first).json()["agents"][0]["instructions"] == payload["instructions"]
    assert client.get("/agents/mine", headers=second).json() == {"agents": []}
    assert client.put(f"/agents/mine/{agent_id}", headers=second, json=payload).status_code == 404
    assert AgentCatalog(path).list_student_agents("school", "first")[0].name == "故事精灵"

    updated = client.put(f"/agents/mine/{agent_id}", headers=first, json={**payload, "name": "月球向导"})
    assert updated.json()["name"] == "月球向导"
    assert client.delete(f"/agents/mine/{agent_id}", headers=first).status_code == 200
    assert client.get("/agents/mine", headers=first).json() == {"agents": []}


def test_student_profile_rejects_empty_instructions(tmp_path):
    auth = AuthService(users={"student": UserRecord("student", "school", "student", hash_password("password"))})
    client = TestClient(create_app(auth, agent_catalog=AgentCatalog(tmp_path / "agents.sqlite")))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]
    response = client.post("/agents/mine", headers={"Authorization": f"Bearer {token}"}, json={"name": "空白", "instructions": "  ", "description": "", "category": "通用", "providerId": "model"})
    assert response.status_code == 422
    missing_model = client.post("/agents/mine", headers={"Authorization": f"Bearer {token}"}, json={"name": "空白", "instructions": "认真回答", "description": "", "category": "通用", "providerId": "  "})
    assert missing_model.status_code == 422
