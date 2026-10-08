import sys
import types

import pytest

from apps.api.app.models.calls import PostgresModelCallLog


pytestmark = pytest.mark.unit


def test_postgres_model_call_log_uses_parameterized_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[tuple[str, object]] = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def execute(self, query, values=None): executed.append((query, values))
        def fetchall(self): return []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def cursor(self): return Cursor()
    module = types.SimpleNamespace(connect=lambda url: Connection())
    monkeypatch.setitem(sys.modules, "psycopg", module)

    log = PostgresModelCallLog("postgresql://example")
    log.record("org-1", "provider-1", "text", "succeeded")

    assert any("values (%s, %s, %s, %s, now())" in query for query, _ in executed)
