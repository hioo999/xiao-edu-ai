from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Protocol


class MediaJobQueue(Protocol):
    def enqueue(self, job_id: str) -> None: ...
    def dequeue(self, timeout_seconds: int = 1) -> str | None: ...
    def dead_letter(self, job_id: str, error: str) -> None: ...
    def list_dead_letters(self, limit: int = 100) -> list[dict[str, str]]: ...
    def retry_dead_letter(self, job_id: str) -> bool: ...


class RedisMediaJobQueue:
    """Redis-backed wake-up queue; PostgreSQL remains the durable job source."""

    def __init__(self, redis_url: str, queue_name: str = "xiao-edu:media-jobs") -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis media queue requires redis") from exc
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._queue_name = queue_name
        self._dead_letter_queue_name = f"{queue_name}:dead-letter"
        self._heartbeat_key = f"{queue_name}:worker-heartbeat"

    def enqueue(self, job_id: str) -> None:
        self._client.lpush(self._queue_name, job_id)

    def dequeue(self, timeout_seconds: int = 1) -> str | None:
        item = self._client.brpop(self._queue_name, timeout=timeout_seconds)
        return item[1] if item else None

    def dead_letter(self, job_id: str, error: str) -> None:
        self._client.lpush(self._dead_letter_queue_name, f"{job_id}|{error[:500]}")

    def list_dead_letters(self, limit: int = 100) -> list[dict[str, str]]:
        entries = self._client.lrange(self._dead_letter_queue_name, 0, max(0, limit - 1))
        dead_letters = []
        for entry in entries:
            job_id, separator, error = entry.partition("|")
            if separator and job_id:
                dead_letters.append({"jobId": job_id, "error": error})
        return dead_letters

    def retry_dead_letter(self, job_id: str) -> bool:
        for entry in self._client.lrange(self._dead_letter_queue_name, 0, -1):
            if entry.partition("|")[0] == job_id:
                self._client.lrem(self._dead_letter_queue_name, 1, entry)
                self.enqueue(job_id)
                return True
        return False

    def heartbeat(self) -> None:
        self._client.set(self._heartbeat_key, datetime.now(timezone.utc).isoformat(), ex=120)

    def worker_status(self) -> dict[str, object]:
        heartbeat = self._client.get(self._heartbeat_key)
        return {"queueDepth": self._client.llen(self._queue_name), "deadLetterDepth": self._client.llen(self._dead_letter_queue_name), "lastHeartbeat": heartbeat, "workerReady": bool(heartbeat)}


class LedgerMediaJobQueue:
    """SQLite/PG durable-ledger queue for single-node deployments without Redis.

    The worker polls the ledger directly, so enqueue/dequeue are no-ops here.
    Dead letters and worker heartbeats are stored alongside the job ledger.
    """

    def __init__(self, ledger) -> None:
        self._ledger = ledger

    def enqueue(self, job_id: str) -> None:
        return None

    def dequeue(self, timeout_seconds: int = 1) -> str | None:
        return None

    def dead_letter(self, job_id: str, error: str) -> None:
        self._ledger.mark_dead_letter(job_id, error)

    def list_dead_letters(self, limit: int = 100) -> list[dict[str, str]]:
        return self._ledger.list_dead_letters(limit)

    def retry_dead_letter(self, job_id: str) -> bool:
        return self._ledger.retry_dead_letter(job_id)

    def clear_dead_letters(self) -> int:
        return self._ledger.clear_dead_letters()

    def heartbeat(self) -> None:
        self._ledger.heartbeat()

    def worker_status(self) -> dict[str, object]:
        return self._ledger.worker_status()


def build_media_job_queue(ledger=None) -> MediaJobQueue | None:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        return RedisMediaJobQueue(redis_url)
    return LedgerMediaJobQueue(ledger) if ledger is not None else None
