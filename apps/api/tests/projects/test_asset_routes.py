from fastapi.testclient import TestClient
from pathlib import Path

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.classrooms.assistance import AssistanceManager


def classroom_manager() -> AssistanceManager:
    manager = AssistanceManager()
    manager.create("class-001", "org-001").teachers = {"teacher-001"}
    manager.open("class-001")
    return manager


def test_teacher_can_filter_review_queue_and_students_only_see_approved_showcase() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-001"),
        "viewer": UserRecord("student-002", "org-001", "student", hash_password("password")),
    })
    catalog = CreativeAssetCatalog()
    pending = catalog.create(project_id="p-1", organization_id="org-001", owner_user_id="student-001", kind="image", title="海洋小屋", preview_url="", prompt="海洋")
    approved = catalog.create(project_id="p-2", organization_id="org-001", owner_user_id="student-001", kind="webpage", title="星空网页", preview_url="", prompt="星空")
    catalog.review(approved.asset_id, "org-001", "approved", True)
    client = TestClient(create_app(auth_service=auth, creative_asset_catalog=catalog, assistance_manager=classroom_manager()))
    teacher_login = client.post("/auth/login", json={"username": "teacher", "password": "password"})
    student_login = client.post("/auth/login", json={"username": "student", "password": "password"})
    viewer_login = client.post("/auth/login", json={"username": "viewer", "password": "password"})
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['accessToken']}"}
    student_headers = {"Authorization": f"Bearer {student_login.json()['accessToken']}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['accessToken']}"}

    filtered = client.get("/works/review?kind=webpage&featured=true", headers=teacher_headers)
    showcase = client.get("/works/showcase?kind=webpage", headers=student_headers)

    assert [work["assetId"] for work in filtered.json()["works"]] == [approved.asset_id]
    assert [work["assetId"] for work in showcase.json()["works"]] == [approved.asset_id]
    assert pending.asset_id not in [work["assetId"] for work in showcase.json()["works"]]
    assert client.get(f"/works/{approved.asset_id}", headers=viewer_headers).status_code == 200
    assert client.get(f"/works/{pending.asset_id}", headers=viewer_headers).status_code == 403

    batch = client.post("/works/review/batch", headers=teacher_headers, json={"assetIds": [pending.asset_id], "state": "approved", "featured": False})
    assert batch.status_code == 200
    assert batch.json()["reviewed"] == 1

    liked = client.post(f"/works/{approved.asset_id}/like", headers=student_headers, json={"enabled": True})
    assert liked.status_code == 200 and liked.json()["likeCount"] == 1
    assert client.post(f"/works/{approved.asset_id}/comments", headers=student_headers, json={"body": "很棒的星空网页！"}).status_code == 403
    commented = client.post(f"/works/{approved.asset_id}/comments", headers=teacher_headers, json={"body": "很棒的星空网页！"})
    assert commented.status_code == 200
    comments = client.get(f"/works/{approved.asset_id}/comments", headers=student_headers)
    assert comments.json()["comments"][0]["body"] == "很棒的星空网页！"


def test_share_revoke_cannot_cross_organization_boundary() -> None:
    auth = AuthService(users={
        "owner": UserRecord("owner-001", "org-001", "student", hash_password("password")),
        "admin": UserRecord("admin-002", "org-002", "organization_admin", hash_password("password")),
    })
    catalog = CreativeAssetCatalog()
    asset = catalog.create(project_id="p-1", organization_id="org-001", owner_user_id="owner-001", kind="image", title="作品", preview_url="", prompt="作品")
    catalog.review(asset.asset_id, "org-001", "approved", False)
    client = TestClient(create_app(auth_service=auth, creative_asset_catalog=catalog))
    owner_login = client.post("/auth/login", json={"username": "owner", "password": "password"})
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['accessToken']}"}
    link = client.post("/shares", headers=owner_headers, json={"assetId": asset.asset_id}).json()["token"]
    admin_login = client.post("/auth/admin/login", json={"username": "admin", "password": "password"})

    response = client.post(f"/shares/{link}/revoke", headers={"Authorization": f"Bearer {admin_login.json()['accessToken']}"})

    assert response.status_code == 404


def test_staff_can_edit_persisted_work_metadata_and_private_work_stays_hidden(tmp_path: Path) -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-001"),
        "viewer": UserRecord("student-002", "org-001", "student", hash_password("password")),
    })
    catalog_path = tmp_path / "assets.sqlite3"
    catalog = CreativeAssetCatalog(catalog_path)
    work = catalog.create(project_id="p-1", organization_id="org-001", owner_user_id="student-001", kind="video", title="魔法书", preview_url="/samples/magic-book.mp4", prompt="翻开魔法书")
    catalog.review(work.asset_id, "org-001", "approved", True)
    client = TestClient(create_app(auth_service=auth, creative_asset_catalog=catalog, assistance_manager=classroom_manager()))
    teacher_token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    student_token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]
    viewer_token = client.post("/auth/login", json={"username": "viewer", "password": "password"}).json()["accessToken"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    saved = client.put(f"/works/{work.asset_id}/metadata", headers=teacher_headers, json={
        "title": "魔法书翻开", "coverUrl": "/covers/magic-book.jpg", "processSteps": ["选一个故事", "请 AI 添上星光"],
        "gradeMin": 3, "gradeMax": 5, "visibility": "private", "isExample": True,
    })

    assert saved.status_code == 200
    assert saved.json()["processSteps"] == ["选一个故事", "请 AI 添上星光"]
    assert saved.json()["isExample"] is True
    assert client.get(f"/works/{work.asset_id}", headers={"Authorization": f"Bearer {student_token}"}).status_code == 200
    assert client.get(f"/works/{work.asset_id}", headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403
    assert work.asset_id not in [item["assetId"] for item in client.get("/works/showcase", headers={"Authorization": f"Bearer {viewer_token}"}).json()["works"]]

    persisted = CreativeAssetCatalog(catalog_path).get(work.asset_id, "org-001")
    assert persisted.cover_url == "/covers/magic-book.jpg"
    assert persisted.grade_max == 5
    assert persisted.visibility == "private"


def test_students_cannot_edit_work_metadata() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    catalog = CreativeAssetCatalog()
    work = catalog.create(project_id="p-1", organization_id="org-001", owner_user_id="student-001", kind="image", title="小猫", preview_url="", prompt="小猫")
    client = TestClient(create_app(auth_service=auth, creative_asset_catalog=catalog))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.put(f"/works/{work.asset_id}/metadata", headers={"Authorization": f"Bearer {token}"}, json={"title": "不该保存"})

    assert response.status_code == 403


def test_staff_can_upload_cover_and_preview_media_for_an_approved_work(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHOWCASE_MEDIA_STORAGE_PATH", str(tmp_path / "showcase-media"))
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-001"),
    })
    catalog = CreativeAssetCatalog()
    work = catalog.create(project_id="p-1", organization_id="org-001", owner_user_id="student-001", kind="video", title="魔法城堡", preview_url="", prompt="城堡")
    catalog.review(work.asset_id, "org-001", "approved", True)
    client = TestClient(create_app(auth_service=auth, creative_asset_catalog=catalog, assistance_manager=classroom_manager()))
    teacher_token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    student_token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {teacher_token}"}

    cover = client.post(f"/works/{work.asset_id}/media/cover", headers=headers, files={"file": ("cover.png", b"\x89PNG\r\n\x1a\ncover", "image/png")})
    preview = client.post(f"/works/{work.asset_id}/media/preview", headers=headers, files={"file": ("castle.mp4", b"fake-mp4-content", "video/mp4")})

    assert cover.status_code == 200
    assert cover.json()["work"]["coverUrl"] == f"/works/{work.asset_id}/media/cover"
    assert preview.status_code == 200
    assert preview.json()["work"]["previewUrl"] == f"/works/{work.asset_id}/media/preview"
    media = client.get(f"/works/{work.asset_id}/media/preview", headers={"Authorization": f"Bearer {student_token}"})
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("video/mp4")
    assert media.content == b"fake-mp4-content"
