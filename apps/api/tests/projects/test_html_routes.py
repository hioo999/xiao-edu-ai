from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.projects.html_service import HtmlWorkspaceService
from apps.api.app.projects.artifact_storage import WorkArtifactStore
from packages.agent_runtime.src.dispatcher import AgentExecutionResult


class FakeDispatcher:
    def dispatch(self, request, prompt: str, *, organization_id: str) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_kind="html",
            html=f"<main>{prompt}</main>",
            teaching_steps=["先确定主题"],
        )


def test_authenticated_student_can_generate_html_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORK_ARTIFACT_STORAGE_PATH", str(tmp_path / "artifacts"))
    auth = AuthService(
        users={
            "student-001": UserRecord(
                user_id="student-001",
                organization_id="org-001",
                role="student",
                password_hash=hash_password("student-password"),
            ),
            "student-002": UserRecord("student-002", "org-001", "student", hash_password("other-password")),
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
    downloaded = client.get(f"/works/{response.json()['assetId']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.text == "<main>做一个海底世界网页</main>"
    other_login = client.post("/auth/login", json={"username": "student-002", "password": "other-password"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['accessToken']}"}
    assert client.get(f"/works/{response.json()['assetId']}/download", headers=other_headers).status_code == 403
    WorkArtifactStore(tmp_path / "artifacts").delete(response.json()["assetId"], "org-001")
    legacy_download = client.get(f"/works/{response.json()['assetId']}/download", headers=headers)
    assert legacy_download.status_code == 200
    assert legacy_download.text == "<main>做一个海底世界网页</main>"
    client.post("/projects/project-001/html/generate", headers=headers, json={"prompt": "把网页改成星空主题"})
    original_snapshot = client.get(f"/works/{response.json()['assetId']}/download", headers=headers)
    assert original_snapshot.text == "<main>做一个海底世界网页</main>"


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
    reopened = client.get("/projects/project-001/html", headers=headers)
    assert reopened.json()["currentVersion"]["html"] == "<main>第一版</main>"
