import pytest

from apps.api.app.reports.service import LearningEvent, ReportService


def test_student_report_contains_only_owned_learning_events() -> None:
    service = ReportService(
        [
            LearningEvent("student-001", "lesson.completed", "网页课程"),
            LearningEvent("student-002", "lesson.completed", "其他课程"),
        ]
    )

    report = service.for_student("student-001")

    assert report["studentId"] == "student-001"
    assert report["completedLessons"] == ["网页课程"]


def test_unknown_student_report_is_denied() -> None:
    service = ReportService([])

    with pytest.raises(PermissionError):
        service.for_student("student-001")
