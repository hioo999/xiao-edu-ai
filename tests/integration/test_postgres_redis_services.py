import os
import sqlite3
import uuid

import pytest

from apps.api.app.media.jobs import JobState, PostgresMediaJobLedger
from apps.api.app.media.queue import RedisMediaJobQueue
from scripts.migrate_sqlite_to_postgres import migrate


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres_url() -> str:
    value = os.getenv("POSTGRES_INTEGRATION_URL")
    if not value:
        pytest.skip("set POSTGRES_INTEGRATION_URL to run real PostgreSQL integration tests")
    return value


@pytest.fixture(scope="module")
def redis_url() -> str:
    value = os.getenv("REDIS_INTEGRATION_URL")
    if not value:
        pytest.skip("set REDIS_INTEGRATION_URL to run real Redis integration tests")
    return value


def test_postgres_media_ledger_persists_a_claim_across_instances(postgres_url: str) -> None:
    producer = PostgresMediaJobLedger(postgres_url)
    job = producer.create("image", "student-integration", organization_id="org-integration", prompt="画一棵树")
    producer.start(job.job_id)
    producer.update_progress(job.job_id, 40)

    worker = PostgresMediaJobLedger(postgres_url)
    persisted = worker.get(job.job_id)

    assert persisted.state is JobState.RUNNING
    assert persisted.attempts == 1
    assert persisted.progress == 40


def test_redis_media_queue_round_trip_and_dead_letter(redis_url: str) -> None:
    queue_name = f"xiao-edu:integration:{uuid.uuid4().hex}"
    queue = RedisMediaJobQueue(redis_url, queue_name)
    try:
        queue.enqueue("job-integration")
        assert queue.dequeue(timeout_seconds=1) == "job-integration"
        queue.dead_letter("job-integration", "provider timeout")
        assert queue.list_dead_letters() == [{"jobId": "job-integration", "error": "provider timeout"}]
        assert queue.retry_dead_letter("job-integration") is True
        assert queue.dequeue(timeout_seconds=1) == "job-integration"
    finally:
        queue._client.delete(queue_name, f"{queue_name}:dead-letter", f"{queue_name}:worker-heartbeat")


def test_sqlite_to_postgres_migration_rehearsal(postgres_url: str, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite_path = tmp_path / "platform.db"
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("""create table platform_users (
            username text primary key, user_id text, organization_id text, role text,
            password_hash text, enabled integer, expires_at text, class_id text)""")
        connection.execute("insert into platform_users values (?, ?, ?, ?, ?, ?, ?, ?)", ("migration-student", "student-migration", "org-migration", "student", "hash", 1, None, "class-migration"))

    monkeypatch.setenv("PLATFORM_DB_PATH", str(sqlite_path))
    copied = migrate(sqlite_path, postgres_url)

    assert copied["platform_users"] == 1
    import psycopg
    with psycopg.connect(postgres_url) as connection, connection.cursor() as cursor:
        cursor.execute("select user_id, organization_id from platform_users where username = %s", ("migration-student",))
        assert cursor.fetchone() == ("student-migration", "org-migration")
