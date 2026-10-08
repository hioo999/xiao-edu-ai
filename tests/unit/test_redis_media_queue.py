import sys
import types

import pytest

from apps.api.app.media.queue import RedisMediaJobQueue


pytestmark = pytest.mark.unit


def test_redis_media_queue_pushes_and_pops_job_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    class Client:
        def lpush(self, queue_name, job_id): calls.append(("lpush", (queue_name, job_id)))
        def brpop(self, queue_name, timeout):
            calls.append(("brpop", (queue_name, timeout)))
            return (queue_name, "job-1")
    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *_args, **_kwargs: Client())))
    queue = RedisMediaJobQueue("redis://example")
    queue.enqueue("job-1")
    assert queue.dequeue() == "job-1"
    assert calls[0][0] == "lpush"


def test_redis_media_queue_writes_dead_letters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    class Client:
        def lpush(self, queue_name, payload): calls.append((queue_name, payload))
    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *_args, **_kwargs: Client())))
    queue = RedisMediaJobQueue("redis://example")
    queue.dead_letter("job-1", "provider unavailable")
    assert calls == [("xiao-edu:media-jobs:dead-letter", "job-1|provider unavailable")]


def test_redis_media_queue_requeues_a_dead_letter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    class Client:
        def lrange(self, _name, _start, _stop): return ["job-1|provider unavailable"]
        def lrem(self, name, count, entry): calls.append(("lrem", (name, count, entry)))
        def lpush(self, name, value): calls.append(("lpush", (name, value)))
    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *_args, **_kwargs: Client())))
    queue = RedisMediaJobQueue("redis://example")
    assert queue.retry_dead_letter("job-1") is True
    assert calls[0][0] == "lrem"
    assert calls[1] == ("lpush", ("xiao-edu:media-jobs", "job-1"))


def test_redis_media_queue_reports_worker_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def set(self, _key, _value, ex): assert ex == 120
        def get(self, _key): return "2026-10-01T00:00:00+00:00"
        def llen(self, key): return 2 if key.endswith("dead-letter") else 5
    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *_args, **_kwargs: Client())))
    queue = RedisMediaJobQueue("redis://example")
    queue.heartbeat()
    assert queue.worker_status() == {"queueDepth": 5, "deadLetterDepth": 2, "lastHeartbeat": "2026-10-01T00:00:00+00:00", "workerReady": True}
