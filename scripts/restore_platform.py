from __future__ import annotations

import argparse
from pathlib import Path
import tarfile
import tempfile


ALLOWED_MEMBERS = {"platform.db", "provider-encryption.key"}
ALLOWED_PREFIXES = ("course-materials/", "generated-assets/")


def restore_platform(archive_path: Path, destination: Path) -> None:
    """Restore a trusted platform backup, rejecting archive path traversal."""

    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if any(member.name.startswith("/") or ".." in Path(member.name).parts for member in members):
            raise ValueError("backup contains an unsafe path")
        if any(member.name not in ALLOWED_MEMBERS and not member.name.startswith(ALLOWED_PREFIXES) for member in members):
            raise ValueError("backup contains an unexpected file")
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary_directory:
            staging = Path(temporary_directory)
            archive.extractall(staging, filter="data")
            destination.mkdir(parents=True, exist_ok=True)
            for source in staging.iterdir():
                target = destination / source.name
                if target.exists() and target.is_file():
                    target.unlink()
                if source.is_dir():
                    import shutil
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    import shutil
                    shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a verified AI learning platform backup.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    arguments = parser.parse_args()
    restore_platform(arguments.archive, arguments.data_dir)
    print("restore completed")


if __name__ == "__main__":
    main()
