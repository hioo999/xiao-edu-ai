import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def test_teacher_can_save_and_search_personal_knowledge_content() -> None:
    auth = AuthService(users={"teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password"))})
    client = TestClient(create_app(auth))
    login = client.post("/auth/login", json={"username": "teacher", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    saved = client.post(
        "/knowledge",
        headers=headers,
        json={"scope": "teacher", "scopeId": "teacher-001", "title": "网页课堂", "content": "先观察页面结构，再设计按钮"},
    )
    searched = client.get("/knowledge/search", headers=headers, params={"query": "按钮"})

    assert saved.status_code == 200
    assert saved.json()["content"] == "先观察页面结构，再设计按钮"
    assert [item["document_id"] for item in searched.json()["documents"]] == [saved.json()["document_id"]]
