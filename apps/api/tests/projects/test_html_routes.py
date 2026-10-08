from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.projects.html_service import HtmlWorkspaceService
from packages.agent_runtime.src.dispatcher import AgentExecutionResult


class FakeDispatcher:
    def dispatch(self, request, prompt: str, *, organization_id: str) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_kind="html",
            html=f"<main>{prompt}</main>",
            teaching_steps=["先确定主题"],
        )


def test_authenticated_student_can_generate_html_version() -> None:
    auth = AuthService(
        users={
            "student-001": UserRecord(
                user_id="student-001",
                organization_id="org-001",
                role="student",
                password_hash=hash_password("student-password"),
            )
        }
    )
    client = TestClient(create_app(auth_service=auth, html_service=HtmlWorkspaceService(FakeDispatcher())))
    login = client.post("/auth/login", json={"username": "student-001", "password": "student-password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    response = client.post(
        "/projects/project-001/html/generate",
        headers=headers,
        json={"prompt": "做一个海底世界网页"},
    )

    assert response.status_code == 200
    assert response.json()["assetId"].startswith("asset-")
    assert response.json()["currentVersion"]["versionId"] == "project-001-v1"
    assert response.json()["currentVersion"]["html"] == "<main>做一个海底世界网页</main>"


def test_html_generation_requires_authenticated_student() -> None:
    response = TestClient(create_app()).post(
        "/projects/project-001/html/generate",
        json={"prompt": "做一个网页"},
    )

    assert response.status_code == 401


def test_student_can_list_restore_and_download_own_html_versions() -> None:
    auth = AuthService(users={"student-001": UserRecord("student-001", "org-001", "student", hash_password("student-password"))})
    client = TestClient(create_app(auth_service=auth, html_service=HtmlWorkspaceService(FakeDispatcher())))
    login = client.post("/auth/login", json={"username": "student-001", "password": "student-password"})
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    client.post("/projects/project-001/html/generate", headers=headers, json={"prompt": "第一版"})
    client.post("/projects/project-001/html/generate", headers=headers, json={"prompt": "第二版"})

    versions = client.get("/projects/project-001/html", headers=headers)
    restore = client.post("/projects/project-001/html/versions/project-001-v1/restore", headers=headers)
    downloaded = client.get("/projects/project-001/html/download", headers=headers)

    assert [item["versionId"] for item in versions.json()["versions"]] == ["project-001-v1", "project-001-v2"]
    assert restore.json()["currentVersionId"] == "project-001-v1"
    assert downloaded.text == "<main>第一版</main>"
