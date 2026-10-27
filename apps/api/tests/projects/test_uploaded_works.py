from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.classrooms.assistance import AssistanceManager


def classroom_manager() -> AssistanceManager:
    manager = AssistanceManager()
    manager.create("class-001", "org-001").teachers = {"teacher-001"}
    manager.open("class-001")
    return manager


def test_teacher_uploads_a_static_html_work_then_admin_approves_it_for_students() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "admin": UserRecord("admin-001", "org-001", "organization_admin", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password")),
    })
    client = TestClient(create_app(auth_service=auth))
    headers = {role: {"Authorization": f"Bearer {client.post('/auth/admin/login' if role == 'admin' else '/auth/login', json={'username': role, 'password': 'password'}).json()['accessToken']}"} for role in ("teacher", "admin", "student")}

    uploaded = client.post("/works/upload", headers=headers["teacher"], data={"title": "太阳系小网站"}, files={"file": ("solar.html", b"<h1>solar</h1>", "text/html")})

    assert uploaded.status_code == 200
    work = uploaded.json()
    assert work["uploadMode"] == "static_html"
    assert work["artifact"]["filename"] == "solar.html"
    assert client.get(f"/works/{work['assetId']}/download", headers=headers["teacher"]).content == b"<h1>solar</h1>"

    assert client.post(f"/works/{work['assetId']}/review", headers=headers["admin"], json={"state": "approved", "featured": True}).status_code == 200
    showcase = client.get("/works/showcase", headers=headers["student"])
    assert [item["assetId"] for item in showcase.json()["works"]] == [work["assetId"]]


def test_teacher_can_upload_a_zip_but_not_an_executable_project_file() -> None:
    auth = AuthService(users={"teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    package = client.post("/works/upload", headers=headers, files={"file": ("fullstack-site.zip", b"zip-bytes", "application/zip")})
    rejected = client.post("/works/upload", headers=headers, files={"file": ("server.py", b"print('no')", "text/x-python")})

    assert package.status_code == 200
    assert package.json()["uploadMode"] == "deployment_package"
    assert rejected.status_code == 422


def test_teacher_can_import_a_work_into_a_student_portfolio() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-001"),
    })
    client = TestClient(create_app(auth_service=auth, assistance_manager=classroom_manager()))
    teacher_token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    response = client.post("/works/upload", headers={"Authorization": f"Bearer {teacher_token}"}, data={"ownerUserId": "student-001"}, files={"file": ("student.html", b"<p>student</p>", "text/html")})

    assert response.status_code == 200
    assert response.json()["ownerUserId"] == "student-001"


def test_showcase_popular_order_prefers_favorites_then_likes() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "student-a": UserRecord("student-a", "org-001", "student", hash_password("password"), class_id="class-001"),
        "student-b": UserRecord("student-b", "org-001", "student", hash_password("password")),
        "student-c": UserRecord("student-c", "org-001", "student", hash_password("password")),
    })
    client = TestClient(create_app(auth_service=auth, assistance_manager=classroom_manager()))
    headers = {name: {"Authorization": f"Bearer {client.post('/auth/login', json={'username': name, 'password': 'password'}).json()['accessToken']}"} for name in ("teacher", "student-a", "student-b", "student-c")}
    works = []
    for title in ("星空城堡", "魔法书", "彩虹小龙"):
        item = client.post("/works", headers=headers["student-a"], json={"projectId": title, "kind": "text", "title": title, "prompt": title}).json()
        client.post(f"/works/{item['assetId']}/review", headers=headers["teacher"], json={"state": "approved", "featured": False})
        works.append(item)

    client.post(f"/works/{works[0]['assetId']}/like", headers=headers["student-b"], json={"enabled": True})
    client.post(f"/works/{works[1]['assetId']}/like", headers=headers["student-b"], json={"enabled": True})
    client.post(f"/works/{works[1]['assetId']}/favorite", headers=headers["student-c"], json={"enabled": True})
    client.post(f"/works/{works[2]['assetId']}/favorite", headers=headers["student-b"], json={"enabled": True})
    client.post(f"/works/{works[2]['assetId']}/favorite", headers=headers["student-c"], json={"enabled": True})

    showcase = client.get("/works/showcase?sort=popular&limit=8", headers=headers["student-a"])

    assert showcase.status_code == 200
    assert [item["title"] for item in showcase.json()["works"]] == ["彩虹小龙", "魔法书", "星空城堡"]
    assert showcase.json()["works"][0]["favoriteCount"] == 2
    assert showcase.json()["works"][1]["likeCount"] == 1
