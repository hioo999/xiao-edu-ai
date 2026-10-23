import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.auth.routes import create_auth_router
from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.classrooms.routes import create_classroom_router
from apps.api.app.auth.provisioning_routes import create_provisioning_router
from apps.api.app.reports.routes import create_report_router
from apps.api.app.reports.service import LearningEvent, ReportService
from apps.api.app.projects.asset_routes import create_asset_router
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.projects.artifact_storage import WorkArtifactStore
from apps.api.app.projects.interactions import WorkInteractionStore
from apps.api.app.projects.deployments import DeploymentService
from apps.api.app.projects.showcase_media import ShowcaseMediaStore
from apps.api.app.courses.catalog import CourseCatalog, CourseRecord
from apps.api.app.courses.routes import create_course_router
from apps.api.app.courses.learning_routes import create_learning_router
from apps.api.app.courses.learning import LearningStore
from apps.api.app.courses.storage import CourseMaterialStore
from apps.api.app.sharing.routes import create_share_router
from apps.api.app.sharing.links import ShareLinkService
from apps.api.app.media.routes import create_media_router
from apps.api.app.media.jobs import MediaJobLedger, JobState
from apps.api.app.media.queue import LedgerMediaJobQueue
from apps.api.app.knowledge.routes import create_knowledge_router
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.knowledge.scopes import KnowledgeScope


pytestmark = pytest.mark.integration


@pytest.fixture
def teaching_context():
    password_hash = hash_password("password123")
    auth = AuthService({
        "teacher": UserRecord("teacher", "school", "teacher", password_hash),
        "admin": UserRecord("admin", "school", "organization_admin", password_hash),
        "first": UserRecord("first", "school", "student", password_hash, class_id="first-class"),
        "second": UserRecord("second", "school", "student", password_hash, class_id="second-class"),
        "outsider": UserRecord("outsider", "other-school", "student", password_hash, class_id="foreign-class"),
    })
    classrooms = AssistanceManager()
    classrooms.create("first-class", "school").teachers = {"teacher"}
    classrooms.create("second-class", "school").teachers = {"another-teacher"}
    classrooms.create("foreign-class", "other-school").teachers = {"teacher"}
    application = FastAPI()
    application.include_router(create_auth_router(auth), prefix="/auth")
    application.include_router(create_classroom_router(auth, classrooms))
    client = TestClient(application)
    headers = {}
    for username in ("teacher", "admin", "first", "second"):
        response = client.post("/auth/login", json={"username": username, "password": "password123"})
        headers[username] = {"Authorization": f"Bearer {response.json()['accessToken']}"}
    return application, client, auth, classrooms, headers


@pytest.mark.parametrize("suffix", ["", "/students"])
def test_teacher_cannot_read_unassigned_classroom(teaching_context, suffix):
    _, client, _, _, headers = teaching_context
    response = client.get(f"/classrooms/second-class{suffix}", headers=headers["teacher"])
    assert response.status_code == 403
    assert client.get(f"/classrooms/first-class{suffix}", headers=headers["teacher"]).status_code == 200
    assert client.get(f"/classrooms/second-class{suffix}", headers=headers["admin"]).status_code == 200


def test_student_cannot_report_presence_in_another_class(teaching_context):
    _, client, _, classrooms, headers = teaching_context
    response = client.post("/classrooms/second-class/presence", headers=headers["first"], json={"activeFeature": "html"})
    assert response.status_code == 403
    assert classrooms.students_for_classroom("second-class") == []


def test_teacher_student_directory_is_filtered_before_pagination(teaching_context):
    application, client, auth, classrooms, headers = teaching_context
    application.include_router(create_provisioning_router(auth, classrooms=classrooms))
    response = client.get("/organizations/school/students?limit=1", headers=headers["teacher"])
    assert response.status_code == 200
    assert [student["userId"] for student in response.json()["students"]] == ["first"]
    assert client.get("/organizations/school/students?classId=second-class", headers=headers["teacher"]).status_code == 403
    assert len(client.get("/organizations/school/students", headers=headers["admin"]).json()["students"]) == 2


def test_teacher_cannot_provision_students_into_another_class(teaching_context):
    application, client, auth, classrooms, headers = teaching_context
    application.include_router(create_provisioning_router(auth, classrooms=classrooms))
    request = {"prefix": "new", "count": 1, "classId": "second-class", "initialPassword": "password123"}
    response = client.post("/organizations/school/students/batch", headers=headers["teacher"], json=request)
    assert response.status_code == 403
    assert auth.user_for_id("new-001") is None
    request["classId"] = "first-class"
    assert client.post("/organizations/school/students/batch", headers=headers["teacher"], json=request).status_code == 200


def test_reports_enforce_classroom_and_organization_scope(teaching_context):
    application, client, auth, classrooms, headers = teaching_context
    reports = ReportService([LearningEvent(student, "lesson.completed", "AI课") for student in ("first", "second", "outsider")])
    application.include_router(create_report_router(auth, reports, classrooms=classrooms))
    assert client.get("/reports/students/first", headers=headers["teacher"]).status_code == 200
    assert client.get("/reports/students/second", headers=headers["teacher"]).status_code == 403
    assert client.get("/reports/students/outsider", headers=headers["admin"]).status_code == 403


@pytest.fixture
def work_context(teaching_context, tmp_path):
    application, client, auth, classrooms, headers = teaching_context
    catalog = CreativeAssetCatalog(tmp_path / "works.db")
    assets = {}
    for owner in ("first", "second", "outsider"):
        assets[owner] = catalog.create(project_id="demo", organization_id="other-school" if owner == "outsider" else "school", owner_user_id=owner, kind="webpage", title=owner, preview_url="", prompt="", visibility="private")
    application.include_router(create_asset_router(
        auth, catalog, classrooms=classrooms,
        artifact_store=WorkArtifactStore(tmp_path / "artifacts"),
        interactions=WorkInteractionStore(tmp_path / "interactions"),
        deployments=DeploymentService(tmp_path / "deployments"),
        showcase_media=ShowcaseMediaStore(tmp_path / "showcase"),
    ))
    return client, headers, catalog, assets


def test_teacher_review_list_contains_only_assigned_students(work_context):
    client, headers, _, assets = work_context
    response = client.get("/works/review", headers=headers["teacher"])
    assert response.status_code == 200
    assert [work["assetId"] for work in response.json()["works"]] == [assets["first"].asset_id]


@pytest.mark.parametrize("method,suffix,payload", [
    ("GET", "", None),
    ("GET", "/download", None),
    ("GET", "/comments", None),
    ("GET", "/media/cover", None),
    ("GET", "/deployments", None),
    ("POST", "/review", {"state": "approved"}),
    ("PUT", "/metadata", {"title": "unauthorized edit"}),
    ("POST", "/comments", {"body": "unauthorized feedback"}),
    ("POST", "/like", {"enabled": True}),
    ("POST", "/favorite", {"enabled": True}),
])
def test_teacher_cannot_access_other_class_private_work(work_context, method, suffix, payload):
    client, headers, catalog, assets = work_context
    response = client.request(method, f"/works/{assets['second'].asset_id}{suffix}", headers=headers["teacher"], json=payload)
    assert response.status_code == 403
    assert catalog.get(assets["second"].asset_id, "school").title == "second"


def test_mixed_batch_review_is_rejected_before_any_mutation(work_context):
    client, headers, catalog, assets = work_context
    response = client.post("/works/review/batch", headers=headers["teacher"], json={"assetIds": [assets["first"].asset_id, assets["second"].asset_id], "state": "approved"})
    assert response.status_code == 403
    assert catalog.get(assets["first"].asset_id, "school").review_state == "pending"


def test_public_work_can_be_read_but_not_managed_by_other_teacher(work_context):
    client, headers, catalog, assets = work_context
    asset_id = assets["second"].asset_id
    catalog.update_metadata(asset_id, "school", visibility="organization")
    catalog.review(asset_id, "school", "approved", False)
    assert client.get(f"/works/{asset_id}", headers=headers["teacher"]).status_code == 200
    assert client.put(f"/works/{asset_id}/metadata", headers=headers["teacher"], json={"title": "stolen"}).status_code == 403
    assert client.get(f"/works/{asset_id}", headers=headers["first"]).status_code == 200


def test_private_work_cannot_be_liked_or_comments_read_by_another_student(work_context):
    client, headers, _, assets = work_context
    path = f"/works/{assets['second'].asset_id}"
    assert client.post(f"{path}/like", headers=headers["first"], json={"enabled": True}).status_code == 403
    assert client.get(f"{path}/comments", headers=headers["first"]).status_code == 403


@pytest.fixture
def course_context(teaching_context, tmp_path):
    application, client, auth, classrooms, headers = teaching_context
    courses = CourseCatalog(tmp_path / "courses.db")
    courses.save(CourseRecord("shared", "school", "another-teacher", "共享课程", "", teacher_script="老师专属逐字稿"))
    courses.publish_to_class("shared", "first-class", "school")
    courses.publish_to_class("shared", "second-class", "school")
    courses.save(CourseRecord("private", "school", "another-teacher", "未授权草稿", ""))
    learning = LearningStore(tmp_path / "learning.db")
    submissions = {}
    for student in ("first", "second"):
        learning.upsert_progress(student, "shared", "school", 50, False, 1)
        submissions[student] = learning.submit_homework(student, "shared", "school", "我的作品")
    application.include_router(create_course_router(auth, CourseMaterialStore(tmp_path / "materials"), courses, classrooms=classrooms))
    application.include_router(create_learning_router(auth, courses, learning, classrooms=classrooms))
    return client, headers, courses, learning, submissions


def test_teacher_only_reads_own_or_assigned_course(course_context):
    client, headers, _, _, _ = course_context
    assert client.get("/courses/private", headers=headers["teacher"]).status_code == 403
    assert client.get("/courses/shared", headers=headers["teacher"]).status_code == 200
    assert [course["courseId"] for course in client.get("/courses", headers=headers["teacher"]).json()["courses"]] == ["shared"]


def test_teacher_cannot_overwrite_or_delete_another_authors_course(course_context):
    client, headers, courses, _, _ = course_context
    assert client.post("/courses", headers=headers["teacher"], json={"courseId": "shared", "title": "覆盖"}).status_code == 403
    assert client.delete("/courses/shared", headers=headers["teacher"]).status_code == 403
    assert courses.get("shared", "school").title == "共享课程"


def test_teacher_cannot_change_publication_in_another_class(course_context):
    client, headers, courses, _, _ = course_context
    response = client.post("/courses/shared/unpublish", headers=headers["teacher"], json={"classId": "second-class"})
    assert response.status_code == 403
    assert len(courses.list_for_class("second-class", "school")) == 1


def test_student_course_payload_does_not_expose_teacher_script(course_context):
    client, headers, _, _, _ = course_context
    response = client.get("/courses/classrooms/first-class/published", headers=headers["first"])
    assert response.status_code == 200
    assert "teacherScript" not in response.json()["courses"][0]


def test_teacher_course_reports_exclude_other_class_students(course_context):
    client, headers, _, _, _ = course_context
    progress = client.get("/learning/courses/shared/progress", headers=headers["teacher"])
    submissions = client.get("/learning/courses/shared/submissions", headers=headers["teacher"])
    assert progress.status_code == submissions.status_code == 200
    assert [record["studentId"] for record in progress.json()["progress"]] == ["first"]
    assert [record["studentId"] for record in submissions.json()["submissions"]] == ["first"]


def test_teacher_cannot_annotate_other_class_submission(course_context):
    client, headers, _, learning, submissions = course_context
    submission_id = submissions["second"].submission_id
    response = client.post(f"/learning/submissions/{submission_id}/annotate", headers=headers["teacher"], json={"feedback": "不应修改"})
    assert response.status_code == 403
    assert learning.get_submission(submission_id, "school").status == "submitted"


def test_teacher_cannot_share_or_revoke_other_class_work(teaching_context, work_context):
    application, _, auth, classrooms, _ = teaching_context
    client, headers, catalog, assets = work_context
    application.include_router(create_share_router(auth, ShareLinkService(), catalog, classrooms=classrooms))
    asset_id = assets["second"].asset_id
    catalog.review(asset_id, "school", "approved", False)
    response = client.post("/shares", headers=headers["teacher"], json={"assetId": asset_id})
    assert response.status_code == 403
    link = client.post("/shares", headers=headers["second"], json={"assetId": asset_id}).json()
    assert client.post(f"/shares/{link['token']}/revoke", headers=headers["teacher"]).status_code == 403


def test_media_monitoring_retry_and_dead_letters_respect_data_scope(teaching_context, tmp_path):
    application, client, auth, classrooms, headers = teaching_context
    ledger = MediaJobLedger(tmp_path / "jobs.db")
    jobs = {}
    for student, organization in (("first", "school"), ("second", "school"), ("outsider", "other-school")):
        job = ledger.create("image", student, organization_id=organization)
        ledger.start(job.job_id)
        ledger.fail(job.job_id, "test failure")
        ledger.mark_dead_letter(job.job_id, "test failure")
        jobs[student] = job.job_id
    application.include_router(create_media_router(auth, ledger, classrooms=classrooms, queue=LedgerMediaJobQueue(ledger)))
    listed = client.get("/media/jobs/operations", headers=headers["teacher"])
    assert [job["ownerUserId"] for job in listed.json()["jobs"]] == ["first"]
    assert client.get(f"/media/jobs/{jobs['second']}", headers=headers["teacher"]).status_code == 403
    assert client.post(f"/media/jobs/{jobs['second']}/operations/retry", headers=headers["teacher"]).status_code == 403
    assert ledger.get(jobs["second"]).state == JobState.FAILED
    dead_letters = client.get("/media/jobs/operations/dead-letters", headers=headers["admin"])
    assert {job["jobId"] for job in dead_letters.json()["jobs"]} == {jobs["first"], jobs["second"]}
    assert client.post(f"/media/jobs/operations/dead-letters/{jobs['outsider']}/retry", headers=headers["admin"]).status_code == 404


def test_teacher_knowledge_directory_does_not_expose_private_documents(teaching_context):
    application, client, auth, classrooms, headers = teaching_context
    knowledge = KnowledgeCatalog()
    common = knowledge.add(KnowledgeScope.ORGANIZATION, "school", "课堂资料", "school")
    personal = knowledge.add(KnowledgeScope.TEACHER, "teacher", "自己的资料", "school")
    other = knowledge.add(KnowledgeScope.TEACHER, "another-teacher", "其他老师私有资料", "school")
    knowledge.add(KnowledgeScope.STUDENT, "first", "学生私人资料", "school")
    application.include_router(create_knowledge_router(auth, knowledge, classrooms=classrooms))
    listed = client.get("/knowledge", headers=headers["teacher"])
    assert {document["document_id"] for document in listed.json()["documents"]} == {common.document_id, personal.document_id}
    found = client.get("/knowledge/search?query=资料", headers=headers["teacher"])
    assert {document["document_id"] for document in found.json()["documents"]} == {common.document_id, personal.document_id}
    assert client.delete(f"/knowledge/{other.document_id}", headers=headers["teacher"]).status_code == 403
    assert client.delete(f"/knowledge/{common.document_id}", headers=headers["teacher"]).status_code == 403
    assert client.delete(f"/knowledge/{personal.document_id}", headers=headers["teacher"]).status_code == 200


def test_teacher_cannot_create_knowledge_in_another_users_scope(teaching_context):
    application, client, auth, classrooms, headers = teaching_context
    application.include_router(create_knowledge_router(auth, KnowledgeCatalog(), classrooms=classrooms))
    response = client.post("/knowledge", headers=headers["teacher"], json={"title": "越权资料", "scope": "teacher", "scopeId": "another-teacher"})
    assert response.status_code == 403


def test_assistance_cannot_be_granted_for_a_student_in_another_class(teaching_context):
    _, client, _, classrooms, headers = teaching_context
    classrooms.open("first-class")
    response = client.post("/classrooms/first-class/assistance", headers=headers["teacher"], json={"studentId": "second"})
    assert response.status_code == 403
    assert not classrooms.can_act_as("first-class", "teacher", "second")
    assert client.post("/classrooms/first-class/assistance", headers=headers["teacher"], json={"studentId": "first"}).status_code == 200
