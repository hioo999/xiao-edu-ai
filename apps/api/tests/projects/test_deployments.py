from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.projects.deployments import (
    DeploymentService,
    DeploymentUnavailableError,
    TencentDeployer,
    ZipProjectAnalyzer,
)


def make_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_zip_analyzer_recognizes_node_project_dependencies_and_env_template() -> None:
    content = make_zip({
        "index.html": "<h1>hello</h1>",
        "package.json": json.dumps({"dependencies": {"express": "^4.18.0"}, "devDependencies": {"vite": "^5.0.0"}}),
        ".env.example": "DATABASE_URL=\nSECRET_TOKEN=\n",
    })

    manifest = ZipProjectAnalyzer().analyze(content)

    assert manifest["projectType"] == "node"
    assert "express" in manifest["dependencies"]
    assert "vite" in manifest["dependencies"]
    assert manifest["entrypoints"] == ["index.html"]
    assert set(manifest["envTemplate"]) == {"DATABASE_URL", "SECRET_TOKEN"}


def test_zip_analyzer_falls_back_to_static_and_raises_for_invalid_zip() -> None:
    static_manifest = ZipProjectAnalyzer().analyze(make_zip({"index.html": "<h1>static</h1>"}))

    assert static_manifest["projectType"] == "static"
    assert static_manifest["dependencies"] == []
    with pytest.raises(zipfile.BadZipFile):
        ZipProjectAnalyzer().analyze(b"not-a-zip")


def test_deployment_service_persists_records_and_isolates_organizations(tmp_path) -> None:
    service = DeploymentService(tmp_path / "deployments.sqlite3")
    manifest = {"projectType": "node", "dependencies": ["express"]}

    record = service.create("asset-1", "org-1", manifest, {"DATABASE_URL": ""})
    reloaded = DeploymentService(tmp_path / "deployments.sqlite3")

    assert reloaded.get(record.deployment_id, "org-1").asset_id == "asset-1"
    assert reloaded.list_for_asset("asset-1", "org-1")[0].state == "prepared"
    assert reloaded.list_for_asset("asset-1", "org-2") == []
    with pytest.raises(KeyError):
        reloaded.get(record.deployment_id, "org-2")

    published = service.publish(record.deployment_id, "org-1", "https://works.example.edu/solar-system")
    assert published.state == "published"
    assert DeploymentService(tmp_path / "deployments.sqlite3").get(record.deployment_id, "org-1").published_url == "https://works.example.edu/solar-system"


def test_tencent_deployer_requires_credentials_before_live_deploy() -> None:
    deployer = TencentDeployer()

    with pytest.raises(DeploymentUnavailableError):
        deployer.validate_credentials({})
    deployer.validate_credentials({
        "TENCENT_SECRET_ID": "id",
        "TENCENT_SECRET_KEY": "key",
        "TENCENT_REGION": "ap-guangzhou",
    })


def test_teacher_uploads_zip_and_prepares_deployment_record() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
    })
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    package = make_zip({"index.html": "<h1>site</h1>", "package.json": "{\"dependencies\":{\"next\":\"14\"}}"})

    uploaded = client.post("/works/upload", headers=headers, files={"file": ("site.zip", package, "application/zip")})

    assert uploaded.status_code == 200
    asset_id = uploaded.json()["assetId"]
    deployment = uploaded.json()["deployment"]
    assert deployment["projectType"] == "node"
    assert deployment["state"] == "prepared"
    listing = client.get(f"/works/{asset_id}/deployments", headers=headers)
    assert listing.status_code == 200
    assert [item["deploymentId"] for item in listing.json()["deployments"]] == [deployment["deploymentId"]]
    detail = client.get(f"/works/{asset_id}/deployments/{deployment['deploymentId']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["manifest"]["dependencies"] == ["next"]


def test_deployment_prepare_rejects_non_zip_artifacts() -> None:
    auth = AuthService(users={"teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    uploaded = client.post("/works/upload", headers=headers, files={"file": ("page.html", b"<p>html</p>", "text/html")})
    asset_id = uploaded.json()["assetId"]

    rejected = client.post(f"/works/{asset_id}/deployments/prepare", headers=headers)

    assert rejected.status_code == 422


def test_teacher_can_register_https_preview_for_prepared_project() -> None:
    auth = AuthService(users={"teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    package = make_zip({"index.html": "<h1>site</h1>", "package.json": "{\"dependencies\":{\"next\":\"14\"}}"})
    uploaded = client.post("/works/upload", headers=headers, files={"file": ("site.zip", package, "application/zip")}).json()
    deployment_id = uploaded["deployment"]["deploymentId"]

    rejected = client.put(f"/works/{uploaded['assetId']}/deployments/{deployment_id}/publish", headers=headers, json={"previewUrl": "http://unsafe.example.edu"})
    published = client.put(f"/works/{uploaded['assetId']}/deployments/{deployment_id}/publish", headers=headers, json={"previewUrl": "https://works.example.edu/solar-system"})

    assert rejected.status_code == 422
    assert published.status_code == 200
    assert published.json()["deployment"]["state"] == "published"
    assert published.json()["deployment"]["publishedUrl"] == "https://works.example.edu/solar-system"
    assert published.json()["work"]["previewUrl"] == "https://works.example.edu/solar-system"
