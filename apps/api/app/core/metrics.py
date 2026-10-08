from __future__ import annotations

import os
import threading


class MetricsRegistry:
    """Thread-safe in-process counters and gauges for health and alerts."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            return {**self._counters, **self._gauges}


class QueueBacklogMonitor:
    """Reads queue health and emits threshold-based alerts without external services."""

    def __init__(self, queue) -> None:
        self._queue = queue
        self._backlog_threshold = max(1, int(os.getenv("QUEUE_BACKLOG_ALERT_THRESHOLD", "50")))
        self._dead_letter_threshold = max(1, int(os.getenv("DEAD_LETTER_ALERT_THRESHOLD", "10")))

    def status(self) -> dict[str, object]:
        status = getattr(self._queue, "worker_status", None)
        if not callable(status):
            return {"queueDepth": 0, "deadLetterDepth": 0, "workerReady": False, "lastHeartbeat": None}
        return status()

    def alerts(self) -> list[dict[str, str]]:
        state = self.status()
        alerts: list[dict[str, str]] = []
        queue_depth = int(state.get("queueDepth") or 0)
        dead_letter_depth = int(state.get("deadLetterDepth") or 0)
        if queue_depth >= self._backlog_threshold:
            alerts.append({"severity": "warning", "code": "queue_backlog", "message": f"media queue depth {queue_depth} exceeds threshold {self._backlog_threshold}"})
        if dead_letter_depth >= self._dead_letter_threshold:
            alerts.append({"severity": "critical", "code": "dead_letter_backlog", "message": f"dead-letter depth {dead_letter_depth} exceeds threshold {self._dead_letter_threshold}"})
        if not state.get("workerReady"):
            alerts.append({"severity": "info", "code": "worker_not_ready", "message": "media worker queue is not configured or has no recent heartbeat"})
        return alerts
