import tarfile

import pytest

from scripts.restore_platform import restore_platform


pytestmark = pytest.mark.unit


def test_restore_platform_restores_allowed_backup_content(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "platform.db").write_bytes(b"database")
    archive_path = tmp_path / "backup.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source / "platform.db", arcname="platform.db")

    destination = tmp_path / "restored"
    restore_platform(archive_path, destination)

    assert (destination / "platform.db").read_bytes() == b"database"


def test_restore_platform_rejects_path_traversal(tmp_path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    payload = tmp_path / "payload"
    payload.write_text("unsafe")
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload, arcname="../unsafe")

    with pytest.raises(ValueError, match="unsafe path"):
        restore_platform(archive_path, tmp_path / "restored")
