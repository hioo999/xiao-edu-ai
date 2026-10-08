from fastapi.testclient import TestClient
from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app

def test_teacher_imports_an_inspiration_attachment() -> None:
    auth = AuthService(users={"teacher": UserRecord("t", "org", "teacher", hash_password("pw")), "student": UserRecord("s", "org", "student", hash_password("pw"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "teacher", "password": "pw"}).json()["accessToken"]
    response = client.post("/inspiration/import", headers={"Authorization": f"Bearer {token}"}, data={"title":"星空","prompt":"做一个星空网页"}, files={"file": ("star.png", b"image", "image/png")})
    assert response.status_code == 200
    assert response.json()["attachmentFilename"] == "star.png"
