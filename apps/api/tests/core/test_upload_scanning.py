from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.core.scanning import LocalHeuristicScanner, UnsafeUploadError, build_upload_scanner, scan_upload
from apps.api.app.main import create_app


def test_local_scanner_blocks_executables_and_active_scripts() -> None:
    scanner = LocalHeuristicScanner()

    assert scanner.scan(b"\x7fELFmalware").safe is False
    assert scanner.scan(b"MZmalware").safe is False
    assert scanner.scan(b"#!/bin/sh\nrm -rf").safe is False
    assert scanner.scan(b"<?php echo 1;").safe is False
    assert scanner.scan(b"<h1>hello</h1>").safe is True
    assert scanner.scan(b"<html><script>alert(1)</script></html>").safe is True
    assert scanner.scan(b"PK\x03\x04zip-bytes").safe is True


def test_scan_upload_raises_for_unsafe_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAMAV_HOST", raising=False)

    with pytest.raises(UnsafeUploadError):
        scan_upload(build_upload_scanner(), b"\x7fELFmalware")


def test_work_upload_rejects_executable_disguised_as_html() -> None:
    auth = AuthService(users={"teacher": UserRecord("teacher-1", "org-1", "teacher", hash_password("password"))})
    client = TestClient(create_app(auth_service=auth))
    token = client.post("/auth/login", json={"username": "teacher", "password": "password"}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    rejected = client.post("/works/upload", headers=headers, files={"file": ("page.html", b"\x7fELFmalware", "text/html")})

    assert rejected.status_code == 422
    assert "blocked" in rejected.json()["detail"]
