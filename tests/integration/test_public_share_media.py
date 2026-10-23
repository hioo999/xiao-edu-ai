from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.projects.showcase_media import ShowcaseMediaStore
from apps.api.app.sharing.links import ShareLinkService


def test_public_share_media_uses_share_token_and_stops_after_revoke(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOWCASE_MEDIA_STORAGE_PATH", str(tmp_path / "media"))
    auth = AuthService(users={"student": UserRecord("student", "school", "student", hash_password("password"))})
    assets = CreativeAssetCatalog()
    links = ShareLinkService()
    asset = assets.create(project_id="art", organization_id="school", owner_user_id="student", kind="image", title="森林", preview_url="", prompt="森林")
    media = ShowcaseMediaStore(tmp_path / "media")
    media.save(asset.asset_id, "school", "preview", "forest.png", "image/png", b"image-bytes")
    assets.update_metadata(asset.asset_id, "school", preview_url=f"/works/{asset.asset_id}/media/preview")
    assets.review(asset.asset_id, "school", "approved", False)
    client = TestClient(create_app(auth_service=auth, creative_asset_catalog=assets, share_link_service=links))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    share = client.post("/shares", headers=headers, json={"assetId": asset.asset_id}).json()["token"]

    preview = client.get(f"/shares/public/{share}/media/preview")
    assert preview.status_code == 200
    assert preview.content == b"image-bytes"
    assert preview.headers["content-type"] == "image/png"
    assert client.get("/shares/public/invalid/media/preview").status_code == 404
    assert client.get(f"/shares/public/{share}/media/other").status_code == 404

    assert client.post(f"/shares/{share}/revoke", headers=headers).status_code == 200
    assert client.get(f"/shares/public/{share}/media/preview").status_code == 404
