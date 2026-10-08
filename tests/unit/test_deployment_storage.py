import sys
import types

import pytest

from apps.api.app.core.deployment import DeploymentStorage, deployment_storage_from_env, storage_is_ready


pytestmark = pytest.mark.unit


def test_sqlite_mode_remains_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLATFORM_STORAGE_MODE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    assert deployment_storage_from_env().mode == "sqlite"


def test_postgres_mode_requires_a_valid_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_STORAGE_MODE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "mysql://invalid")

    with pytest.raises(RuntimeError, match="PostgreSQL"):
        deployment_storage_from_env()


def test_postgres_readiness_uses_a_select_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement): assert statement == "select 1"
        def fetchone(self): return (1,)

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    assert storage_is_ready(DeploymentStorage("postgres", "postgresql://example", None), "unused.db") is True
