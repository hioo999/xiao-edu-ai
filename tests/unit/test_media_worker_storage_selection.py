import pytest
from cryptography.fernet import Fernet

from apps.api.app.media import worker


pytestmark = pytest.mark.unit


def test_worker_uses_postgres_services_when_storage_mode_is_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_STORAGE_MODE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("PROVIDER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(worker, "PostgresProviderRegistry", lambda *_args: "providers")
    monkeypatch.setattr(worker, "PostgresMediaJobLedger", lambda *_args: "jobs")
    monkeypatch.setattr(worker, "PostgresCreativeAssetCatalog", lambda *_args: "assets")
    monkeypatch.setattr(worker, "PostgresUsageLedger", lambda *_args: "usage")
    monkeypatch.setattr(worker, "PostgresModelCallLog", lambda *_args: "calls")
    monkeypatch.setattr(worker, "MediaProviderGateway", lambda _providers: "gateway")
    monkeypatch.setattr(worker, "build_asset_store", lambda: None)
    monkeypatch.setattr(worker, "build_media_job_queue", lambda _ledger: None)
    captured: dict[str, object] = {}
    def capture_worker(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()
    monkeypatch.setattr(worker, "MediaGenerationWorker", capture_worker)

    worker.build_worker()

    assert captured["args"] == ("jobs", "providers", "assets", "gateway", "usage")
    assert captured["kwargs"] == {"asset_store": None, "call_log": "calls", "queue": None}
