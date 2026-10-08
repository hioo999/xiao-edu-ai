import pytest

from apps.api.app.auth.provisioning import (
    CsvValidationError,
    provision_students,
    validate_student_csv,
)


def test_batch_provisioning_skips_collisions_and_returns_credentials() -> None:
    students = provision_students(
        prefix="class3",
        count=3,
        class_id="class-a",
        initial_password="welcome-123",
        existing_usernames={"class3-001"},
    )

    assert [student.username for student in students] == [
        "class3-002",
        "class3-003",
        "class3-004",
    ]
    assert all(student.initial_password == "welcome-123" for student in students)


def test_csv_validation_rejects_invalid_rows_before_creation() -> None:
    with pytest.raises(CsvValidationError) as error:
        validate_student_csv("name,class\n小明,三年级\n,四年级\n")

    assert error.value.row_errors == {3: "name is required"}


def test_csv_validation_returns_normalized_rows() -> None:
    rows = validate_student_csv("name,class\n小明,三年级\n小红,四年级\n")

    assert rows == [
        {"name": "小明", "class": "三年级"},
        {"name": "小红", "class": "四年级"},
    ]
