from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO


@dataclass(frozen=True)
class ProvisionedStudent:
    username: str
    class_id: str
    initial_password: str


class CsvValidationError(ValueError):
    def __init__(self, row_errors: dict[int, str]) -> None:
        self.row_errors = row_errors
        super().__init__("student CSV contains invalid rows")


def provision_students(
    *,
    prefix: str,
    count: int,
    class_id: str,
    initial_password: str,
    existing_usernames: set[str],
) -> list[ProvisionedStudent]:
    if not prefix.strip() or not class_id.strip():
        raise ValueError("prefix and class_id are required")
    if count < 1 or count > 1000:
        raise ValueError("count must be between 1 and 1000")
    if not initial_password:
        raise ValueError("initial_password is required")

    students: list[ProvisionedStudent] = []
    number = 1
    reserved = set(existing_usernames)
    while len(students) < count:
        username = f"{prefix.strip()}-{number:03d}"
        number += 1
        if username in reserved:
            continue
        reserved.add(username)
        students.append(
            ProvisionedStudent(
                username=username,
                class_id=class_id.strip(),
                initial_password=initial_password,
            )
        )
    return students


def validate_student_csv(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames != ["name", "class"]:
        raise CsvValidationError({1: "CSV headers must be name,class"})

    rows: list[dict[str, str]] = []
    errors: dict[int, str] = {}
    for row_number, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        class_name = (row.get("class") or "").strip()
        if not name:
            errors[row_number] = "name is required"
        elif not class_name:
            errors[row_number] = "class is required"
        else:
            rows.append({"name": name, "class": class_name})
    if errors:
        raise CsvValidationError(errors)
    return rows
