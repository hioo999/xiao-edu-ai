from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tarfile
import tempfile


def backup_platform(data_dir: Path, output_dir: Path, keep: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = output_dir / f"platform-backup-{timestamp}.tar.gz"
    database_path = data_dir / "platform.db"
    key_path = data_dir / "platform.db.provider-key"

    with tempfile.TemporaryDirectory() as temporary_directory:
        snapshot_path = Path(temporary_directory) / "platform.db"
        with sqlite3.connect(database_path) as source, sqlite3.connect(snapshot_path) as destination:
            source.backup(destination)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(snapshot_path, arcname="platform.db")
            if key_path.exists():
                archive.add(key_path, arcname="provider-encryption.key")
            for directory_name in ("course-materials", "generated-assets"):
                directory = data_dir / directory_name
                if directory.exists():
                    archive.add(directory, arcname=directory_name)

    archives = sorted(output_dir.glob("platform-backup-*.tar.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale_archive in archives[keep:]:
        stale_archive.unlink()
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent backup of the platform SQLite database and files.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=7)
    arguments = parser.parse_args()
    if arguments.keep < 1:
        raise SystemExit("--keep must be at least 1")
    archive_path = backup_platform(arguments.data_dir, arguments.output_dir, arguments.keep)
    print(archive_path)


if __name__ == "__main__":
    main()
