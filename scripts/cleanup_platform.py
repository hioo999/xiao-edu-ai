"""Remove expired sessions and stale operational rows from platform SQLite."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3


def existing_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    try:
        return {row[1] for row in connection.execute(f"pragma table_info({table_name})")}
    except sqlite3.OperationalError:
        return set()


def cleanup_expired_sessions(connection: sqlite3.Connection, now: datetime) -> int:
    if "expires_at" not in existing_columns(connection, "access_sessions"):
        return 0
    cursor = connection.execute("delete from access_sessions where expires_at <= ?", (now.isoformat(),))
    return cursor.rowcount if cursor.rowcount is not None else 0


def cleanup_stale_media_jobs(connection: sqlite3.Connection, now: datetime, older_than_days: int) -> int:
    columns = existing_columns(connection, "media_jobs")
    if "state" not in columns or "started_at" not in columns:
        return 0
    threshold = (now - timedelta(days=older_than_days)).isoformat()
    cursor = connection.execute("delete from media_jobs where state in ('succeeded', 'failed') and started_at is not null and started_at <= ?", (threshold,))
    return cursor.rowcount if cursor.rowcount is not None else 0


def cleanup_stale_audit(connection: sqlite3.Connection, now: datetime, older_than_days: int) -> int:
    columns = existing_columns(connection, "audit_records")
    if "created_at" not in columns:
        return 0
    threshold = (now - timedelta(days=older_than_days)).isoformat()
    cursor = connection.execute("delete from audit_records where created_at <= ?", (threshold,))
    return cursor.rowcount if cursor.rowcount is not None else 0


def cleanup_stale_files(directory: Path, now: datetime, older_than_days: int) -> int:
    if not directory.exists():
        return 0
    threshold = now.timestamp() - older_than_days * 86400
    removed = 0
    for path in directory.iterdir():
        if path.is_file() and path.stat().st_mtime < threshold:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def cleanup_platform(database_path: Path, now: datetime | None = None, retention_days: int = 90, artifacts_dir: Path | None = None) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    if not database_path.exists():
        raise FileNotFoundError(database_path)
    with sqlite3.connect(database_path) as connection:
        result = {
            "expiredSessions": cleanup_expired_sessions(connection, current),
            "staleMediaJobs": cleanup_stale_media_jobs(connection, current, retention_days),
            "staleAuditRows": cleanup_stale_audit(connection, current, retention_days),
        }
    if artifacts_dir:
        result["staleArtifactFiles"] = cleanup_stale_files(artifacts_dir, current, retention_days)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean expired sessions and stale platform records.")
    parser.add_argument("--database-path", type=Path, default=os.getenv("PLATFORM_DB_PATH", "var/platform.db"))
    parser.add_argument("--artifacts-dir", type=Path, default=os.getenv("GENERATED_ASSET_STORAGE_PATH", "var/generated-assets"))
    parser.add_argument("--retention-days", type=int, default=90)
    arguments = parser.parse_args()
    if arguments.retention_days < 1:
        raise SystemExit("--retention-days must be at least 1")
    result = cleanup_platform(arguments.database_path, retention_days=arguments.retention_days, artifacts_dir=arguments.artifacts_dir)
    print(result)


if __name__ == "__main__":
    main()
