from io import BytesIO
import zipfile

import pytest

from apps.api.app.courses.file_validation import validate_course_material


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("filename", "content"), [("lesson.pdf", b"%PDF-1.7\nlesson"), ("poster.png", b"\x89PNG\r\n\x1a\nimage"), ("notes.md", b"# lesson")])
def test_course_material_validation_accepts_allowed_safe_files(filename: str, content: bytes) -> None:
    validate_course_material(filename, content)


@pytest.mark.parametrize(("filename", "content", "message"), [("lesson.exe", b"MZ", "file type"), ("lesson.pdf", b"MZ", "executable"), ("poster.png", b"not-an-image", "does not match")])
def test_course_material_validation_rejects_unsafe_or_mismatched_content(filename: str, content: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_course_material(filename, content)


def test_course_material_validation_rejects_archive_path_traversal() -> None:
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../unsafe.txt", "bad")

    with pytest.raises(ValueError, match="unsafe path"):
        validate_course_material("lesson.zip", payload.getvalue())
