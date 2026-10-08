from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from scripts.cleanup_platform import cleanup_expired_sessions, cleanup_platform, cleanup_stale_media_jobs


pytestmark = pytest.mark.unit


def test_cleanup_expired_sessions_removes_only_expired_rows(tmp_path) -> None:
    database = tmp_path / "platform.db"
    now = datetime.now(timezone.utc)
    with sqlite3.connect(database) as connection:
        connection.execute("create table access_sessions (token_hash text, user_id text, organization_id text, role text, expires_at text)")
        connection.execute("insert into access_sessions values ('live', 'u1', 'org1', 'student', ?)", ((now + timedelta(days=1)).isoformat(),))
        connection.execute("insert into access_sessions values ('stale', 'u2', 'org1', 'student', ?)", ((now - timedelta(days=1)).isoformat(),))
    with sqlite3.connect(database) as connection:
        removed = cleanup_expired_sessions(connection, now)
        rows = connection.execute("select token_hash from access_sessions").fetchall()
    assert removed == 1
    assert [row[0] for row in rows] == ["live"]


def test_cleanup_platform_returns_counts_and_requires_existing_database(tmp_path) -> None:
    database = tmp_path / "platform.db"
    now = datetime.now(timezone.utc)
    with sqlite3.connect(database) as connection:
        connection.execute("create table media_jobs (job_id text, state text, started_at text)")
        connection.execute("insert into media_jobs values ('job-1', 'succeeded', ?)", ((now - timedelta(days=200)).isoformat(),))

    result = cleanup_platform(database, now=now, retention_days=90)

    assert result["staleMediaJobs"] == 1
    with pytest.raises(FileNotFoundError):
        cleanup_platform(tmp_path / "missing.db", now=now)
