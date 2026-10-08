from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.media.jobs import MediaJobLedger
from apps.api.app.main import create_app


def test_student_can_submit_and_read_only_own_media_job() -> None:
    service = AuthService(
        users={
            "student-001": UserRecord("student-001", "org-001", "student", hash_password("password")),
            "student-002": UserRecord("student-002", "org-001", "student", hash_password("password")),
        }
    )
    client = TestClient(create_app(service))
    first = client.post("/auth/login", json={"username": "student-001", "password": "password"})
    second = client.post("/auth/login", json={"username": "student-002", "password": "password"})
    first_headers = {"Authorization": f"Bearer {first.json()['accessToken']}"}
    second_headers = {"Authorization": f"Bearer {second.json()['accessToken']}"}

    created = client.post("/media/jobs", headers=first_headers, json={"kind": "image", "prompt": "太空小猫"})
    job_id = created.json()["jobId"]

    assert created.status_code == 202
    assert client.get(f"/media/jobs/{job_id}", headers=first_headers).status_code == 200
    assert client.get(f"/media/jobs/{job_id}", headers=second_headers).status_code == 404
    assert client.post(f"/media/jobs/{job_id}/retry", headers=first_headers).status_code == 409


def test_successful_media_worker_update_creates_a_pending_student_work() -> None:
    service = AuthService(
        users={
            "student-001": UserRecord("student-001", "org-001", "student", hash_password("password")),
            "admin-001": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
        }
    )
    client = TestClient(create_app(service))
    student_login = client.post("/auth/login", json={"username": "student-001", "password": "password"})
    admin_login = client.post("/auth/login", json={"username": "admin-001", "password": "password"})
    student_headers = {"Authorization": f"Bearer {student_login.json()['accessToken']}"}
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

    created = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "太空小猫"})
    job_id = created.json()["jobId"]
    updated = client.post(f"/media/jobs/{job_id}/worker-update", headers=admin_headers, json={"state": "succeeded", "progress": 100})
    works = client.get("/works/mine", headers=student_headers)

    assert updated.status_code == 200
    assert updated.json()["assetId"].startswith("asset-")
    assert works.json()["works"] == [
        {
            "assetId": updated.json()["assetId"],
            "projectId": "image-student-001",
            "ownerUserId": "student-001",
            "kind": "image",
            "title": "image 创作作品",
            "previewUrl": "",
            "coverUrl": "",
            "prompt": "太空小猫",
            "processSteps": [],
            "gradeMin": 3,
            "gradeMax": 6,
            "visibility": "organization",
            "isExample": False,
            "reviewState": "pending",
            "featured": False,
        }
    ]


def test_teacher_can_monitor_and_retry_failed_media_job_in_same_organization() -> None:
    service = AuthService(users={
        "student-001": UserRecord("student-001", "org-001", "student", hash_password("password")),
        "teacher-001": UserRecord("teacher-001", "org-001", "teacher", hash_password("password")),
        "admin-001": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
    })
    client = TestClient(create_app(service))
    student_login = client.post("/auth/login", json={"username": "student-001", "password": "password"})
    teacher_login = client.post("/auth/login", json={"username": "teacher-001", "password": "password"})
    admin_login = client.post("/auth/login", json={"username": "admin-001", "password": "password"})
    student_headers = {"Authorization": f"Bearer {student_login.json()['accessToken']}"}
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['accessToken']}"}
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

    created = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "测试失败任务"})
    job_id = created.json()["jobId"]
    client.post(f"/media/jobs/{job_id}/worker-update", headers=admin_headers, json={"state": "failed", "error": "provider unavailable"})

    operations = client.get("/media/jobs/operations?state=failed", headers=teacher_headers)
    retry = client.post(f"/media/jobs/{job_id}/operations/retry", headers=teacher_headers)

    assert operations.status_code == 200
    assert operations.json()["jobs"][0]["jobId"] == job_id
    assert retry.status_code == 202


def test_admin_can_list_and_retry_sqlite_dead_letters(tmp_path) -> None:
    service = AuthService(users={
        "student-001": UserRecord("student-001", "org-001", "student", hash_password("password")),
        "admin-001": UserRecord("admin-001", "org-001", "platform_admin", hash_password("password")),
    })
    ledger = MediaJobLedger(tmp_path / "media-jobs.sqlite")
    client = TestClient(create_app(service, media_ledger=ledger))
    student_login = client.post("/auth/login", json={"username": "student-001", "password": "password"})
    admin_login = client.post("/auth/login", json={"username": "admin-001", "password": "password"})
    student_headers = {"Authorization": f"Bearer {student_login.json()['accessToken']}"}
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

    created = client.post("/media/jobs", headers=student_headers, json={"kind": "image", "prompt": "测试死信任务"})
    job_id = created.json()["jobId"]
    ledger.start(job_id)
    ledger.fail(job_id, "provider unavailable")
    ledger.mark_dead_letter(job_id, "provider unavailable")

    dead_letters = client.get("/media/jobs/operations/dead-letters", headers=admin_headers)
    retried = client.post(f"/media/jobs/operations/dead-letters/{job_id}/retry", headers=admin_headers)

    assert dead_letters.status_code == 200
    assert dead_letters.json()["jobs"] == [{"jobId": job_id, "error": "provider unavailable"}]
    assert retried.status_code == 202
    assert ledger.get(job_id).state.value == "queued"
