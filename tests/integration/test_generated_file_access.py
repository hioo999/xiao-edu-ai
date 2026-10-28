import base64
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.main import create_app
from apps.api.app.media.jobs import MediaJobLedger
from apps.api.app.media.storage import GeneratedAssetStore
from apps.api.app.projects.catalog import CreativeAssetCatalog


pytestmark = pytest.mark.integration


@pytest.fixture
def generated_files(tmp_path, monkeypatch):
    root = tmp_path / "generated"
    monkeypatch.setenv("GENERATED_ASSET_STORAGE_PATH", str(root))
    monkeypatch.setenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    for variable in ("WORK_ARTIFACT_STORAGE_PATH", "WORK_INTERACTION_STORAGE_PATH", "SHOWCASE_MEDIA_STORAGE_PATH", "DEPLOYMENT_STORAGE_PATH", "LEARNING_STORAGE_PATH"):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))
    password_hash = hash_password("password123")
    auth = AuthService({
        "owner": UserRecord("owner", "school", "student", password_hash, class_id="class-a"),
        "peer": UserRecord("peer", "school", "student", password_hash, class_id="class-b"),
        "teacher": UserRecord("teacher", "school", "teacher", password_hash),
        "admin": UserRecord("admin", "school", "organization_admin", password_hash),
        "foreign": UserRecord("foreign", "other-school", "organization_admin", password_hash),
    })
    classrooms = AssistanceManager()
    classrooms.create("class-a", "school").teachers = {"teacher"}
    classrooms.open("class-a")
    ledger = MediaJobLedger(tmp_path / "jobs.db")
    assets = CreativeAssetCatalog(tmp_path / "assets.db")
    job = ledger.create("image", "owner", organization_id="school")
    content = b"\x89PNG\r\n\x1a\nprivate-art"
    url = GeneratedAssetStore(root, "http://localhost:8000").persist(job.job_id, "data:image/png;base64," + base64.b64encode(content).decode())
    asset = assets.create(project_id="art", organization_id="school", owner_user_id="owner", kind="image", title="森林", preview_url=url, prompt="森林", visibility="private")
    ledger.start(job.job_id)
    ledger.succeed(job.job_id, asset_id=asset.asset_id)
    client = TestClient(create_app(auth_service=auth, assistance_manager=classrooms, media_ledger=ledger, creative_asset_catalog=assets))
    headers = {}
    for username in ("owner", "peer", "teacher", "admin", "foreign"):
        endpoint = "/auth/admin/login" if username in {"admin", "foreign"} else "/auth/login"
        login = client.post(endpoint, json={"username": username, "password": "password123"})
        headers[username] = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    return client, headers, assets, asset, urlsplit(url).path, root, content


def test_raw_generated_files_require_login_and_resource_permission(generated_files):
    client, headers, _, _, path, _, content = generated_files
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers["peer"]).status_code == 403
    assert client.get(path, headers=headers["foreign"]).status_code == 404
    for role in ("owner", "teacher", "admin"):
        response = client.get(path, headers=headers[role])
        assert response.status_code == 200
        assert response.content == content
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-type"] == "image/png"


def test_generated_media_supports_authorized_range_requests(generated_files):
    client, headers, _, _, path, _, content = generated_files
    response = client.get(path, headers={**headers["owner"], "Range": "bytes=0-7"})
    assert response.status_code == 206
    assert response.content == content[:8]
    assert client.head(path).status_code == 401
    assert client.head(path, headers=headers["owner"]).status_code == 200


def test_reference_upload_cannot_be_read_anonymously_or_by_another_student(generated_files):
    client, headers, _, _, _, _, content = generated_files
    uploaded = client.post("/media/jobs/reference-images", headers=headers["owner"], files={"file": ("reference.png", content, "image/png")})
    assert uploaded.status_code == 200
    path = urlsplit(uploaded.json()["referenceImageUrl"]).path
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers["peer"]).status_code == 403
    assert client.get(path, headers=headers["teacher"]).status_code == 403
    assert client.get(path, headers=headers["owner"]).content == content


def test_orphan_files_and_symlinks_are_not_served(generated_files, tmp_path):
    client, headers, _, _, _, root, _ = generated_files
    (root / "orphan.png").write_bytes(b"orphan")
    assert client.get("/generated-assets/orphan.png", headers=headers["owner"]).status_code == 404
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"secret")
    (root / "escape.png").symlink_to(outside)
    assert client.get("/generated-assets/escape.png", headers=headers["owner"]).status_code == 404


def test_approved_generated_work_is_visible_but_revoking_share_revokes_file_access(generated_files):
    client, headers, assets, asset, path, _, content = generated_files
    assets.review(asset.asset_id, "school", "approved", False)
    assets.update_metadata(asset.asset_id, "school", visibility="organization")
    assert client.get(path, headers=headers["peer"]).status_code == 200
    share = client.post("/shares", headers=headers["owner"], json={"assetId": asset.asset_id}).json()["token"]
    public = client.get(f"/shares/public/{share}")
    assert public.json()["work"]["previewUrl"] == f"/shares/public/{share}/media/preview"
    response = client.get(f"/shares/public/{share}/media/preview")
    assert response.status_code == 200
    assert response.content == content
    assert client.post(f"/shares/{share}/revoke", headers=headers["owner"]).status_code == 200
    assert client.get(f"/shares/public/{share}/media/preview").status_code == 404
    assert client.get(path).status_code == 401


def test_share_cannot_be_used_to_publish_another_jobs_file(generated_files):
    client, headers, assets, _, path, _, _ = generated_files
    forged = assets.create(project_id="forged", organization_id="school", owner_user_id="peer", kind="image", title="伪造地址", preview_url="http://localhost:8000" + path, prompt="")
    assets.review(forged.asset_id, "school", "approved", False)
    token = client.post("/shares", headers=headers["peer"], json={"assetId": forged.asset_id}).json()["token"]
    assert client.get(f"/shares/public/{token}/media/preview").status_code == 404


def test_symlinked_job_file_is_denied_even_to_its_owner(generated_files, tmp_path):
    client, headers, _, _, path, root, _ = generated_files
    filename = path.rsplit("/", 1)[-1]
    (root / filename).unlink()
    outside = tmp_path / "private.png"
    outside.write_bytes(b"secret")
    (root / filename).symlink_to(outside)
    assert client.get(path, headers=headers["owner"]).status_code == 404


def test_media_range_headers_are_allowed_by_cors(generated_files):
    client, _, _, _, path, _, _ = generated_files
    response = client.options(path, headers={"Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "HEAD", "Access-Control-Request-Headers": "authorization,range"})
    assert response.status_code == 200
