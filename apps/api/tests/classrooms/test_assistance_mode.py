import pytest

from apps.api.app.classrooms.assistance import AssistanceManager, Classroom, ClassroomState


def test_teacher_can_open_class_and_grant_scoped_assistance() -> None:
    manager = AssistanceManager()
    classroom = manager.create("class-001", "org-001")
    manager.open("class-001")
    grant = manager.grant_assistance("class-001", teacher_id="teacher-001", student_id="student-001")

    assert classroom.state is ClassroomState.OPEN
    assert grant.student_id == "student-001"
    assert manager.can_act_as("class-001", "teacher-001", "student-001") is True


def test_assistance_is_denied_after_class_closes_and_is_audited() -> None:
    manager = AssistanceManager()
    manager.create("class-001", "org-001")
    manager.open("class-001")
    manager.grant_assistance("class-001", teacher_id="teacher-001", student_id="student-001")
    manager.close("class-001")

    assert manager.can_act_as("class-001", "teacher-001", "student-001") is False
    assert manager.audit_events[-1].action == "classroom.closed"


def test_unknown_teacher_cannot_grant_assistance() -> None:
    manager = AssistanceManager()
    manager.create("class-001", "org-001")

    with pytest.raises(PermissionError):
        manager.grant_assistance("class-001", teacher_id="teacher-001", student_id="student-001")
