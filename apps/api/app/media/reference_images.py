from __future__ import annotations

import base64
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


_MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_SIGNATURES = {".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".webp": b"RIFF"}
_MAX_REFERENCE_BYTES = 5 * 1024 * 1024


def reference_folder(organization_id: str, owner_user_id: str) -> Path:
    root = Path(os.getenv("GENERATED_ASSET_STORAGE_PATH", "var/generated-assets")).resolve()
    folder = root
    for part in ("references", organization_id, owner_user_id):
        if not part or part in {".", ".."} or any(character in part for character in "/\\\x00"):
            raise ValueError("reference image identity is invalid")
        folder = folder / part
        if folder.is_symlink():
            raise ValueError("reference image directory is invalid")
    if not folder.resolve().is_relative_to(root):
        raise ValueError("reference image directory is invalid")
    return folder


def valid_reference_payload(extension: str, payload: bytes) -> bool:
    if extension not in _SIGNATURES or not payload or len(payload) > _MAX_REFERENCE_BYTES:
        return False
    if not payload.startswith(_SIGNATURES[extension]):
        return False
    return extension != ".webp" or payload[8:12] == b"WEBP"


def reference_path(reference_url: str, organization_id: str, owner_user_id: str) -> Path:
    public_base = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000").rstrip("/")
    expected_prefix = f"{public_base}/generated-assets/references/{organization_id}/{owner_user_id}/"
    if not reference_url.startswith(expected_prefix):
        raise ValueError("reference image must be uploaded by the current student")
    parsed = urlsplit(reference_url)
    filename = reference_url[len(expected_prefix):]
    if parsed.query or parsed.fragment or not re.fullmatch(r"[A-Za-z0-9_-]{10,}\.(png|jpg|jpeg|webp)", filename):
        raise ValueError("reference image is unavailable or invalid")
    folder = reference_folder(organization_id, owner_user_id)
    path = folder / filename
    if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or not path.is_file():
        raise ValueError("reference image is unavailable or invalid")
    if path.stat().st_size == 0 or path.stat().st_size > _MAX_REFERENCE_BYTES:
        raise ValueError("reference image is unavailable or invalid")
    return path


def reference_data_uri(reference_url: str, organization_id: str, owner_user_id: str) -> str:
    path = reference_path(reference_url, organization_id, owner_user_id)
    payload = path.read_bytes()
    if not valid_reference_payload(path.suffix.lower(), payload):
        raise ValueError("reference image is unavailable or invalid")
    return f"data:{_MIME_TYPES[path.suffix.lower()]};base64,{base64.b64encode(payload).decode('ascii')}"
