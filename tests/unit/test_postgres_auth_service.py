import sys
import types

import pytest

from apps.api.app.auth.service import PostgresAuthService


pytestmark = pytest.mark.unit


def test_postgres_auth_service_initializes_shared_identity_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    statements: list[tuple[str, object]] = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement, values=None): statements.append((statement, values))
        def fetchall(self): return []
        def fetchone(self): return None

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    service = PostgresAuthService({}, "postgresql://example")

    assert service.has_platform_admin() is False
    queries = "\n".join(statement for statement, _ in statements)
    assert "create table if not exists platform_users" in queries
    assert "create table if not exists access_sessions" in queries
    assert "role = %s" in queries
