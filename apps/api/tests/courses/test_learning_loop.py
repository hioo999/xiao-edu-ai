from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.courses.learning import LearningStore


def test_learning_store_tracks_progress_and_annotates_homework(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.sqlite3")

    progress = store.upsert_progress("student-1", "course-1", "org-1", 60, False, 2)
    assert store.get_progress("student-1", "course-1", "org-1").percent == 60
    assert store.list_progress_for_course("course-1", "org-1")[0].student_id == "student-1"
    assert store.list_progress_for_student("student-1", "org-1")[0].completed is False

    submission = store.submit_homework("student-1", "course-1", "org-1", "我的网页作品")
    reviewed = store.annotate(submission.submission_id, "org-1", "继续优化配色", "reviewed")
    assert reviewed.status == "reviewed"
    assert reviewed.teacher_feedback == "继续优化配色"
    assert store.list_submissions_for_course("course-1", "org-1")[0].status == "reviewed"
    with pytest.raises(KeyError):
        store.annotate(submission.submission_id, "org-2", "no", "reviewed")


def test_student_progress_homework_and_teacher_annotation_closed_loop() -> None:
    auth = AuthService(users={
        "teacher": UserRecord("teacher-1", "org-1", "teacher", hash_password("password")),
        "student": UserRecord("student-1", "org-1", "student", hash_password("password"), class_id="class-1"),
    })
    client = TestClient(create_app(auth_service=auth))
    tokens = {}
    for role in ("teacher", "student"):
        tokens[role] = client.post("/auth/login", json={"username": role, "password": "password"}).json()["accessToken"]
    teacher_headers = {"Authorization": f"Bearer {tokens['teacher']}"}
    student_headers = {"Authorization": f"Bearer {tokens['student']}"}

    saved = client.post("/courses", headers=teacher_headers, json={"courseId": "course-1", "title": "网页创作第一课", "blocks": [{"kind": "step", "content": "做一个网页"}]})
    assert saved.status_code == 200
    assert client.post("/courses/course-1/publish", headers=teacher_headers, json={"classId": "class-1"}).status_code == 200

    updated = client.put("/learning/progress/course-1", headers=student_headers, json={"percent": 100, "completed": True, "lastBlockIndex": 1})
    assert updated.status_code == 200
    assert updated.json()["completed"] is True
    submitted = client.post("/learning/courses/course-1/submissions", headers=student_headers, json={"content": "这是我在课上做的网页"})
    assert submitted.status_code == 200
    submission_id = submitted.json()["submissionId"]

    course_progress = client.get("/learning/courses/course-1/progress", headers=teacher_headers)
    assert course_progress.status_code == 200
    assert course_progress.json()["progress"][0]["studentId"] == "student-1"
    course_submissions = client.get("/learning/courses/course-1/submissions", headers=teacher_headers)
    assert course_submissions.json()["submissions"][0]["submissionId"] == submission_id

    annotated = client.post(f"/learning/submissions/{submission_id}/annotate", headers=teacher_headers, json={"feedback": "配色可以更活泼", "status": "reviewed"})
    assert annotated.status_code == 200
    assert annotated.json()["teacherFeedback"] == "配色可以更活泼"

    report = client.get("/reports/me", headers=student_headers)
    assert report.status_code == 200
    assert report.json()["completedLessons"] == ["网页创作第一课"]
    assert report.json()["submittedAssignments"] == ["网页创作第一课"]


def test_student_cannot_access_unpublished_course_learning() -> None:
    auth = AuthService(users={
        "student": UserRecord("student-1", "org-1", "student", hash_password("password"), class_id="class-1"),
    })
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    rejected = client.put("/learning/progress/course-1", headers=headers, json={"percent": 50, "completed": False, "lastBlockIndex": 0})

    assert rejected.status_code == 404
