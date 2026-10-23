from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from apps.api.app.auth.service import AuthService, SessionContext, UserRecord
from apps.api.app.auth.staff_lifecycle import StaffLifecycle, normalize_account_expiry
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.courses.catalog import CourseCatalog, CourseRecord


pytestmark = pytest.mark.unit


def make_lifecycle():
    auth = AuthService({name: UserRecord(name, "school", "organization_admin" if name == "admin" else "teacher", "unused") for name in ("admin", "source", "replacement", "assistant")})
    classrooms = AssistanceManager()
    classrooms.create("class-a", "school").teachers = {"source", "assistant"}
    classrooms.open("class-a")
    classrooms.grant_assistance("class-a", teacher_id="source", student_id="student")
    courses = CourseCatalog()
    courses.save(CourseRecord("course-a", "school", "source", "课程", ""))
    return StaffLifecycle(auth, classrooms, courses), auth, classrooms, courses


def test_memory_handover_preserves_other_teachers_and_revokes_source_session():
    lifecycle, auth, classrooms, courses = make_lifecycle()
    token, _ = auth.create_access_session(SessionContext("source", "school", "teacher"))
    result = lifecycle.handover("school", "source", "replacement", SessionContext("admin", "school", "organization_admin"), "人员交接")
    assert result["classIds"] == ["class-a"]
    assert classrooms.classrooms["class-a"].teachers == {"replacement", "assistant"}
    assert courses.get("course-a", "school").author_user_id == "replacement"
    assert not classrooms.can_act_as("class-a", "source", "student")
    with pytest.raises(PermissionError):
        auth.resolve_access_session(token)
    assert len(lifecycle.history("school", "source")) == 1


def test_mixed_storage_handover_is_rejected_without_partial_changes(tmp_path):
    lifecycle, auth, _, courses = make_lifecycle()
    classrooms = AssistanceManager(tmp_path / "separate.db")
    classrooms.create("class-a", "school")
    classrooms.assign_teachers("class-a", {"source"})
    lifecycle = StaffLifecycle(auth, classrooms, courses)
    with pytest.raises(HTTPException) as rejected:
        lifecycle.handover("school", "source", "replacement", SessionContext("admin", "school", "organization_admin"), "交接")
    assert rejected.value.status_code == 503
    assert auth.user_for_id("source").enabled is True
    assert classrooms.classrooms["class-a"].teachers == {"source"}


def test_expiry_normalizes_local_and_aware_times_to_utc():
    assert normalize_account_expiry(None) is None
    assert normalize_account_expiry(datetime(2099, 1, 1, 18)) == datetime(2099, 1, 1, 10, tzinfo=timezone.utc)
    assert normalize_account_expiry(datetime(2099, 1, 1, 10, tzinfo=timezone.utc)) == datetime(2099, 1, 1, 10, tzinfo=timezone.utc)


def test_disabled_administrator_cannot_finish_a_previously_authenticated_operation():
    lifecycle, auth, _, _ = make_lifecycle()
    actor = SessionContext("admin", "school", "organization_admin")
    auth.set_enabled("admin", "school", False)
    with pytest.raises(HTTPException) as rejected:
        lifecycle.validate_change("school", "replacement", actor, deactivating=True)
    assert rejected.value.status_code == 403
    assert auth.user_for_id("replacement").enabled is True


def test_teacher_cannot_invoke_the_handover_service_as_an_administrator():
    lifecycle, auth, classrooms, _ = make_lifecycle()
    with pytest.raises(HTTPException) as rejected:
        lifecycle.handover("school", "source", "replacement", SessionContext("assistant", "school", "teacher"), "不能越权")
    assert rejected.value.status_code == 403
    assert auth.user_for_id("source").enabled is True
    assert "source" in classrooms.classrooms["class-a"].teachers
