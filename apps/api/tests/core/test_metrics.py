from fastapi.testclient import TestClient

from apps.api.app.core.metrics import MetricsRegistry, QueueBacklogMonitor
from apps.api.app.main import create_app


def test_metrics_registry_counts_and_gauges() -> None:
    registry = MetricsRegistry()
    registry.increment("requests", 2)
    registry.increment("requests")
    registry.set_gauge("queue_depth", 3)

    assert registry.snapshot() == {"requests": 3, "queue_depth": 3}


class FakeQueue:
    def worker_status(self):
        return {"queueDepth": 60, "deadLetterDepth": 2, "workerReady": True, "lastHeartbeat": "now"}


def test_queue_backlog_monitor_raises_backlog_alert() -> None:
    monitor = QueueBacklogMonitor(FakeQueue())

    alerts = monitor.alerts()

    assert any(alert["code"] == "queue_backlog" for alert in alerts)
    assert not any(alert["code"] == "dead_letter_backlog" for alert in alerts)


def test_health_endpoints_expose_metrics_and_alerts() -> None:
    client = TestClient(create_app())
    client.get("/health")

    metrics = client.get("/health/metrics")
    alerts = client.get("/health/alerts")

    assert metrics.status_code == 200
    assert metrics.json()["metrics"]["http.requests.total"] >= 1
    assert "queue" in metrics.json()
    assert alerts.status_code == 200
    assert any(alert["code"] == "worker_not_ready" for alert in alerts.json()["alerts"])
