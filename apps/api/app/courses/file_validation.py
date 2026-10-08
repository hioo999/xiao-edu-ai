from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile


MAX_MATERIAL_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset({"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "md", "png", "jpg", "jpeg", "webp", "mp3", "wav", "mp4", "webm", "zip"})


def validate_course_material(filename: str, content: bytes) -> None:
    """Reject unsafe inputs before course material content reaches persistent storage."""

    safe_name = Path(filename).name
    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if not safe_name or safe_name != filename or len(safe_name) > 180 or extension not in ALLOWED_EXTENSIONS:
        raise ValueError("course material file type is not allowed")
    if not content:
        raise ValueError("course material is empty")
    if len(content) > MAX_MATERIAL_BYTES:
        raise ValueError("course material is too large")
    if content.startswith((b"MZ", b"\x7fELF", b"\xfe\xed\xfa", b"\xcf\xfa\xed\xfe")):
        raise ValueError("executable files are not allowed")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("course material content does not match its file type")
    if extension == "png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("course material content does not match its file type")
    if extension in {"jpg", "jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise ValueError("course material content does not match its file type")
    if extension in {"zip", "docx", "pptx", "xlsx"}:
        _validate_zip(content)


def _validate_zip(content: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            items = archive.infolist()
            if len(items) > 2_000 or sum(item.file_size for item in items) > 200 * 1024 * 1024:
                raise ValueError("compressed course material exceeds safe extraction limits")
            if any(Path(item.filename).is_absolute() or ".." in Path(item.filename).parts for item in items):
                raise ValueError("compressed course material contains an unsafe path")
    except zipfile.BadZipFile as exc:
        raise ValueError("course material is not a valid archive") from exc
