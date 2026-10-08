from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class MediaJob:
    job_id: str
    kind: str
    owner_user_id: str
    organization_id: str = ""
    prompt: str = ""
    project_id: str | None = None
    reference_image_url: str | None = None
    provider_id: str | None = None
    state: JobState = JobState.QUEUED
    error: str | None = None
    asset_id: str | None = None
    external_task_id: str | None = None
    attempts: int = 0
    progress: int = 0
    next_attempt_at: str | None = None
    started_at: str | None = None
    last_heartbeat_at: str | None = None


class MediaJobLedger:
    """Durable queue metadata; a worker owns actual provider invocation."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._jobs: dict[str, MediaJob] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("media persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                create table if not exists media_jobs (
                    job_id text primary key, kind text not null, owner_user_id text not null,
                    organization_id text not null, prompt text not null, project_id text,
                    reference_image_url text,
                    provider_id text, state text not null, error text, asset_id text,
                    external_task_id text, attempts integer not null, progress integer not null,
                    next_attempt_at text, started_at text, last_heartbeat_at text
                )
            """)
            connection.execute("create table if not exists media_dead_letters (job_id text primary key, error text not null, created_at text not null)")
            connection.execute("create table if not exists media_worker_heartbeat (worker_id text primary key, last_heartbeat_at text not null)")
            columns = {row[1] for row in connection.execute("pragma table_info(media_jobs)").fetchall()}
            if "external_task_id" not in columns:
                connection.execute("alter table media_jobs add column external_task_id text")
            if "reference_image_url" not in columns:
                connection.execute("alter table media_jobs add column reference_image_url text")
            if "next_attempt_at" not in columns:
                connection.execute("alter table media_jobs add column next_attempt_at text")
            if "started_at" not in columns:
                connection.execute("alter table media_jobs add column started_at text")
            if "last_heartbeat_at" not in columns:
                connection.execute("alter table media_jobs add column last_heartbeat_at text")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select * from media_jobs").fetchall()
        for row in rows:
            job = MediaJob(job_id=row["job_id"], kind=row["kind"], owner_user_id=row["owner_user_id"], organization_id=row["organization_id"], prompt=row["prompt"], project_id=row["project_id"], reference_image_url=row["reference_image_url"], provider_id=row["provider_id"], state=JobState(row["state"]), error=row["error"], asset_id=row["asset_id"], external_task_id=row["external_task_id"], attempts=row["attempts"], progress=row["progress"], next_attempt_at=row["next_attempt_at"], started_at=row["started_at"], last_heartbeat_at=row["last_heartbeat_at"])
            self._jobs[job.job_id] = job

    def _persist(self, job: MediaJob) -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("""
                insert into media_jobs (job_id, kind, owner_user_id, organization_id, prompt, project_id, reference_image_url, provider_id, state, error, asset_id, external_task_id, attempts, progress, next_attempt_at, started_at, last_heartbeat_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(job_id) do update set kind=excluded.kind, owner_user_id=excluded.owner_user_id, organization_id=excluded.organization_id, prompt=excluded.prompt, project_id=excluded.project_id, reference_image_url=excluded.reference_image_url, provider_id=excluded.provider_id, state=excluded.state, error=excluded.error, asset_id=excluded.asset_id, external_task_id=excluded.external_task_id, attempts=excluded.attempts, progress=excluded.progress, next_attempt_at=excluded.next_attempt_at, started_at=excluded.started_at, last_heartbeat_at=excluded.last_heartbeat_at
            """, (job.job_id, job.kind, job.owner_user_id, job.organization_id, job.prompt, job.project_id, job.reference_image_url, job.provider_id, job.state.value, job.error, job.asset_id, job.external_task_id, job.attempts, job.progress, job.next_attempt_at, job.started_at, job.last_heartbeat_at))

    def create(self, kind: str, owner_user_id: str, *, organization_id: str = "", prompt: str = "", project_id: str | None = None, reference_image_url: str | None = None, provider_id: str | None = None) -> MediaJob:
        job = MediaJob(job_id=f"job-{uuid.uuid4().hex[:12]}", kind=kind, owner_user_id=owner_user_id, organization_id=organization_id, prompt=prompt, project_id=project_id, reference_image_url=reference_image_url, provider_id=provider_id)
        self._jobs[job.job_id] = job
        self._persist(job)
        return job

    def _refresh_from_storage(self) -> None:
        if self._storage_path:
            self._load_storage()

    def get(self, job_id: str) -> MediaJob:
        self._refresh_from_storage()
        return self._jobs[job_id]

    def list_for_owner(self, owner_user_id: str, organization_id: str) -> list[MediaJob]:
        self._refresh_from_storage()
        return [job for job in self._jobs.values() if job.owner_user_id == owner_user_id and job.organization_id == organization_id]

    def list_for_organization(self, organization_id: str, *, state: JobState | None = None, kind: str | None = None) -> list[MediaJob]:
        self._refresh_from_storage()
        jobs = [job for job in self._jobs.values() if job.organization_id == organization_id and (state is None or job.state is state) and (kind is None or job.kind == kind)]
        return sorted(jobs, key=lambda job: job.job_id, reverse=True)

    def list_pending(self) -> list[MediaJob]:
        self._refresh_from_storage()
        now = datetime.now(timezone.utc)
        return [job for job in self._jobs.values() if job.state in {JobState.QUEUED, JobState.RUNNING} and (job.next_attempt_at is None or datetime.fromisoformat(job.next_attempt_at) <= now)]

    def assign_provider(self, job_id: str, provider_id: str) -> None:
        job = self.get(job_id)
        job.provider_id = provider_id
        self._persist(job)

    def set_external_task(self, job_id: str, external_task_id: str) -> None:
        job = self.get(job_id)
        job.external_task_id = external_task_id
        self._persist(job)

    def start(self, job_id: str) -> None:
        job = self.get(job_id)
        if job.state is not JobState.QUEUED:
            raise ValueError("only queued jobs can start")
        now = datetime.now(timezone.utc).isoformat()
        job.state, job.attempts, job.progress = JobState.RUNNING, job.attempts + 1, max(job.progress, 5)
        job.started_at = now
        job.last_heartbeat_at = now
        self._persist(job)

    def update_progress(self, job_id: str, progress: int) -> None:
        job = self.get(job_id)
        if job.state is not JobState.RUNNING:
            raise ValueError("only running jobs can update progress")
        job.progress = max(0, min(99, progress))
        job.last_heartbeat_at = datetime.now(timezone.utc).isoformat()
        self._persist(job)

    def recover_stale_running(self, timeout_seconds: int) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(1, timeout_seconds))
        recovered: list[str] = []
        for job in self._jobs.values():
            if job.state is not JobState.RUNNING:
                continue
            heartbeat = job.last_heartbeat_at or job.started_at
            if heartbeat and datetime.fromisoformat(heartbeat) <= cutoff:
                job.state = JobState.FAILED
                job.error = "worker heartbeat timeout"
                self._persist(job)
                recovered.append(job.job_id)
        return recovered

    def succeed(self, job_id: str, *, asset_id: str) -> None:
        job = self.get(job_id)
        if job.state is not JobState.RUNNING:
            raise ValueError("only running jobs can succeed")
        job.state, job.asset_id, job.progress = JobState.SUCCEEDED, asset_id, 100
        self._persist(job)

    def fail(self, job_id: str, error: str) -> None:
        job = self.get(job_id)
        if job.state is not JobState.RUNNING:
            raise ValueError("only running jobs can fail")
        job.state, job.error = JobState.FAILED, error
        self._persist(job)

    def fail_after_queue(self, job_id: str, error: str) -> None:
        job = self.get(job_id)
        if job.state is not JobState.QUEUED:
            raise ValueError("only queued jobs can fail before start")
        job.state, job.error = JobState.FAILED, error
        self._persist(job)

    def retry(self, job_id: str, *, delay_seconds: int = 0) -> None:
        job = self.get(job_id)
        if job.state is not JobState.FAILED:
            raise ValueError("only failed jobs can retry")
        job.state, job.error, job.progress = JobState.QUEUED, None, 0
        job.next_attempt_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat() if delay_seconds else None
        self._persist(job)

    def mark_dead_letter(self, job_id: str, error: str) -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("insert into media_dead_letters (job_id, error, created_at) values (?, ?, ?) on conflict(job_id) do update set error=excluded.error, created_at=excluded.created_at", (job_id, error[:500], datetime.now(timezone.utc).isoformat()))

    def list_dead_letters(self, limit: int = 100) -> list[dict[str, str]]:
        if not self._storage_path:
            return []
        with self._connect() as connection:
            rows = connection.execute("select job_id, error from media_dead_letters order by created_at desc limit ?", (max(0, limit),)).fetchall()
        return [{"jobId": row["job_id"], "error": row["error"]} for row in rows]

    def retry_dead_letter(self, job_id: str) -> bool:
        if not self._storage_path:
            return False
        with self._connect() as connection:
            cursor = connection.execute("delete from media_dead_letters where job_id = ?", (job_id,))
            deleted = cursor.rowcount
        if not deleted:
            return False
        try:
            self.retry(job_id)
        except (KeyError, ValueError):
            return False
        return True

    def clear_dead_letters(self) -> int:
        if not self._storage_path:
            return 0
        with self._connect() as connection:
            return connection.execute("delete from media_dead_letters").rowcount

    def heartbeat(self, worker_id: str = "default") -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("insert into media_worker_heartbeat (worker_id, last_heartbeat_at) values (?, ?) on conflict(worker_id) do update set last_heartbeat_at=excluded.last_heartbeat_at", (worker_id, datetime.now(timezone.utc).isoformat()))

    def worker_status(self, worker_id: str = "default", heartbeat_window_seconds: int = 90) -> dict[str, object]:
        if not self._storage_path:
            return {"queueDepth": 0, "deadLetterDepth": 0, "workerReady": False, "lastHeartbeat": None}
        with self._connect() as connection:
            row = connection.execute("select last_heartbeat_at from media_worker_heartbeat where worker_id = ?", (worker_id,)).fetchone()
            pending = connection.execute("select count(*) from media_jobs where state in (?, ?)", (JobState.QUEUED.value, JobState.RUNNING.value)).fetchone()[0]
            dead = connection.execute("select count(*) from media_dead_letters").fetchone()[0]
        last_heartbeat = row["last_heartbeat_at"] if row else None
        ready = False
        if last_heartbeat:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_heartbeat)).total_seconds()
                ready = age <= heartbeat_window_seconds
            except ValueError:
                ready = False
        return {"queueDepth": pending, "deadLetterDepth": dead, "workerReady": ready, "lastHeartbeat": last_heartbeat}


class PostgresMediaJobLedger(MediaJobLedger):
    """Shared PostgreSQL media queue metadata for horizontally scaled workers."""

    def __init__(self, database_url: str) -> None:
        self._jobs = {}
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL media jobs require psycopg") from exc
        self._psycopg = psycopg
        self._database_url = database_url
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""create table if not exists media_jobs (
                job_id text primary key, kind text not null, owner_user_id text not null, organization_id text not null,
                prompt text not null, project_id text, reference_image_url text, provider_id text, state text not null,
                error text, asset_id text, external_task_id text, attempts integer not null, progress integer not null,
                next_attempt_at timestamptz, started_at timestamptz, last_heartbeat_at timestamptz)""")
            cursor.execute("alter table media_jobs add column if not exists next_attempt_at timestamptz")
            cursor.execute("alter table media_jobs add column if not exists started_at timestamptz")
            cursor.execute("alter table media_jobs add column if not exists last_heartbeat_at timestamptz")
            cursor.execute("create index if not exists media_jobs_pending_idx on media_jobs (state, job_id)")
            cursor.execute("create table if not exists media_dead_letters (job_id text primary key, error text not null, created_at timestamptz not null)")
            cursor.execute("create table if not exists media_worker_heartbeat (worker_id text primary key, last_heartbeat_at timestamptz not null)")

    def _connect(self):
        return self._psycopg.connect(self._database_url)

    @staticmethod
    def _job(row) -> MediaJob:
        def as_iso(value):
            return value.isoformat() if hasattr(value, "isoformat") else value

        next_attempt_at = as_iso(row[14])
        started_at = as_iso(row[15])
        last_heartbeat_at = as_iso(row[16])
        return MediaJob(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], JobState(row[8]), row[9], row[10], row[11], row[12], row[13], next_attempt_at, started_at, last_heartbeat_at)

    def _persist(self, job: MediaJob) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into media_jobs values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(job_id) do update set kind=excluded.kind, owner_user_id=excluded.owner_user_id, organization_id=excluded.organization_id, prompt=excluded.prompt, project_id=excluded.project_id, reference_image_url=excluded.reference_image_url, provider_id=excluded.provider_id, state=excluded.state, error=excluded.error, asset_id=excluded.asset_id, external_task_id=excluded.external_task_id, attempts=excluded.attempts, progress=excluded.progress, next_attempt_at=excluded.next_attempt_at, started_at=excluded.started_at, last_heartbeat_at=excluded.last_heartbeat_at""", (job.job_id, job.kind, job.owner_user_id, job.organization_id, job.prompt, job.project_id, job.reference_image_url, job.provider_id, job.state.value, job.error, job.asset_id, job.external_task_id, job.attempts, job.progress, job.next_attempt_at, job.started_at, job.last_heartbeat_at))

    def get(self, job_id: str) -> MediaJob:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select * from media_jobs where job_id = %s", (job_id,))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._job(row)

    def start(self, job_id: str) -> None:
        """Atomically claim a queued job so only one worker submits it."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""update media_jobs set state = %s, attempts = attempts + 1,
                progress = greatest(progress, 5), started_at = now(), last_heartbeat_at = now()
                where job_id = %s and state = %s returning job_id""", (JobState.RUNNING.value, job_id, JobState.QUEUED.value))
            if cursor.fetchone() is None:
                raise ValueError("only queued jobs can start")

    def recover_stale_running(self, timeout_seconds: int) -> list[str]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""update media_jobs set state = %s, error = %s
                where state = %s and coalesce(last_heartbeat_at, started_at) < now() - (%s * interval '1 second')
                returning job_id""", (JobState.FAILED.value, "worker heartbeat timeout", JobState.RUNNING.value, max(1, timeout_seconds)))
            return [row[0] for row in cursor.fetchall()]

    def list_for_owner(self, owner_user_id: str, organization_id: str) -> list[MediaJob]:
        return self._list("owner_user_id = %s and organization_id = %s", (owner_user_id, organization_id))

    def list_for_organization(self, organization_id: str, *, state: JobState | None = None, kind: str | None = None) -> list[MediaJob]:
        clauses, values = ["organization_id = %s"], [organization_id]
        if state: clauses.append("state = %s"); values.append(state.value)
        if kind: clauses.append("kind = %s"); values.append(kind)
        return self._list(" and ".join(clauses), tuple(values))

    def list_pending(self) -> list[MediaJob]:
        return self._list("state in (%s, %s) and (next_attempt_at is null or next_attempt_at <= now())", (JobState.QUEUED.value, JobState.RUNNING.value))

    def _list(self, clause: str, values: tuple[object, ...]) -> list[MediaJob]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"select * from media_jobs where {clause} order by job_id desc", values)
            return [self._job(row) for row in cursor.fetchall()]

    def mark_dead_letter(self, job_id: str, error: str) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("insert into media_dead_letters (job_id, error, created_at) values (%s, %s, now()) on conflict(job_id) do update set error=excluded.error, created_at=excluded.created_at", (job_id, error[:500]))

    def list_dead_letters(self, limit: int = 100) -> list[dict[str, str]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select job_id, error from media_dead_letters order by created_at desc limit %s", (max(0, limit),))
            return [{"jobId": row[0], "error": row[1]} for row in cursor.fetchall()]

    def retry_dead_letter(self, job_id: str) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("delete from media_dead_letters where job_id = %s", (job_id,))
            deleted = cursor.rowcount
        if not deleted:
            return False
        try:
            self.retry(job_id)
        except (KeyError, ValueError):
            return False
        return True

    def clear_dead_letters(self) -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("delete from media_dead_letters")
            return cursor.rowcount

    def heartbeat(self, worker_id: str = "default") -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("insert into media_worker_heartbeat (worker_id, last_heartbeat_at) values (%s, now()) on conflict(worker_id) do update set last_heartbeat_at=excluded.last_heartbeat_at", (worker_id,))

    def worker_status(self, worker_id: str = "default", heartbeat_window_seconds: int = 90) -> dict[str, object]:
        def as_iso(value):
            return value.isoformat() if hasattr(value, "isoformat") else value

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select last_heartbeat_at from media_worker_heartbeat where worker_id = %s", (worker_id,))
            row = cursor.fetchone()
            cursor.execute("select count(*) from media_jobs where state in (%s, %s)", (JobState.QUEUED.value, JobState.RUNNING.value))
            pending = cursor.fetchone()[0]
            cursor.execute("select count(*) from media_dead_letters")
            dead = cursor.fetchone()[0]
        last_heartbeat = as_iso(row[0]) if row and row[0] is not None else None
        ready = False
        if last_heartbeat:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_heartbeat)).total_seconds()
                ready = age <= heartbeat_window_seconds
            except ValueError:
                ready = False
        return {"queueDepth": pending, "deadLetterDepth": dead, "workerReady": ready, "lastHeartbeat": last_heartbeat}
