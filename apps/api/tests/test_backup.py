import sqlite3
import tarfile

from scripts.backup_platform import backup_platform
from scripts.preflight_platform import check_environment


def test_backup_contains_database_courses_and_generated_assets(tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with sqlite3.connect(data_dir / "platform.db") as connection:
        connection.execute("create table sample (value text)")
        connection.execute("insert into sample values ('saved')")
    (data_dir / "course-materials").mkdir()
    (data_dir / "course-materials" / "lesson.pdf").write_bytes(b"course")
    (data_dir / "generated-assets").mkdir()
    (data_dir / "generated-assets" / "work.png").write_bytes(b"image")

    archive_path = backup_platform(data_dir, tmp_path / "backups", keep=7)

    with tarfile.open(archive_path) as archive:
        assert set(archive.getnames()) == {"platform.db", "course-materials", "course-materials/lesson.pdf", "generated-assets", "generated-assets/work.png"}


def test_backup_includes_persisted_provider_encryption_key(tmp_path) -> None:
    from scripts.backup_platform import backup_platform
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "platform.db").touch()
    (data_dir / "platform.db.provider-key").write_bytes(b"stable-key")

    archive_path = backup_platform(data_dir, output_dir, 7)

    import tarfile
    with tarfile.open(archive_path, "r:gz") as archive:
        assert "provider-encryption.key" in archive.getnames()


def test_preflight_accepts_a_valid_single_server_configuration(tmp_path) -> None:
    errors, warnings = check_environment(
        {
            "PROVIDER_ENCRYPTION_KEY": "azM6hQeWYBhU6oFFUAhzwSctltmU3TdoQ-lxYj-2OCQ=",
            "PUBLIC_APP_BASE_URL": "https://ai.example.com",
            "CADDY_SITE_ADDRESS": "ai.example.com",
            "PLATFORM_DB_PATH": str(tmp_path / "platform.db"),
            "COURSE_STORAGE_PATH": str(tmp_path / "course-materials"),
            "GENERATED_ASSET_STORAGE_PATH": str(tmp_path / "generated-assets"),
        }
    )

    assert errors == []
    assert warnings == []
