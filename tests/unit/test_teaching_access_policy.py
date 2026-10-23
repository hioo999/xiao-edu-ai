import pytest
from fastapi import HTTPException

from apps.api.app.auth.access import TeachingAccess
from apps.api.app.auth.service import AuthService, SessionContext, UserRecord
from apps.api.app.classrooms.assistance import AssistanceManager


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("role,student,expected", [
    ("teacher", "own", True),
    ("teacher", "other", False),
    ("teacher", "foreign", False),
    ("teacher", "missing", False),
    ("organization_admin", "other", True),
    ("organization_admin", "foreign", False),
    ("student", "own", False),
    ("platform_admin", "foreign", True),
])
def test_student_management_scope(role, student, expected):
    auth = AuthService({
        "own": UserRecord("own", "school", "student", "unused", class_id="assigned"),
        "other": UserRecord("other", "school", "student", "unused", class_id="unassigned"),
        "foreign": UserRecord("foreign", "other-school", "student", "unused", class_id="foreign"),
    })
    classrooms = AssistanceManager()
    classrooms.create("assigned", "school").teachers = {"actor"}
    classrooms.create("foreign", "other-school").teachers = {"actor"}
    access = TeachingAccess(auth, classrooms)
    assert access.can_manage_student(SessionContext("actor", "school", role), student) is expected


def test_missing_classroom_registry_denies_teacher_access():
    access = TeachingAccess(AuthService({}), None)
    teacher = SessionContext("teacher", "school", "teacher")
    assert access.teacher_class_ids(teacher) == set()
    with pytest.raises(HTTPException) as denied:
        access.require_classroom(teacher, "unknown")
    assert denied.value.status_code == 404


def test_reassigning_a_classroom_revokes_access_immediately():
    classrooms = AssistanceManager()
    classrooms.create("assigned", "school").teachers = {"old-teacher"}
    access = TeachingAccess(AuthService({}), classrooms)
    old_teacher = SessionContext("old-teacher", "school", "teacher")
    assert access.require_classroom(old_teacher, "assigned").class_id == "assigned"
    classrooms.assign_teachers("assigned", {"new-teacher"})
    with pytest.raises(HTTPException) as denied:
        access.require_classroom(old_teacher, "assigned")
    assert denied.value.status_code == 403
    assert access.require_classroom(SessionContext("new-teacher", "school", "teacher"), "assigned").class_id == "assigned"
