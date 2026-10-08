import sys
import types

import pytest

from apps.api.app.usage.service import PostgresUsageLedger


pytestmark = pytest.mark.unit


def test_postgres_usage_ledger_reserves_with_row_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[tuple[str, object]] = []

    class Cursor:
        def __init__(self): self.last_query = ""
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, query, values=None):
            self.last_query = query.lower()
            executed.append((query, values))
        def fetchone(self):
            if "from usage_reservations where reservation_id" in self.last_query:
                return None
            return (10,) if "from usage_limits" in self.last_query else (0,)

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    ledger = PostgresUsageLedger("postgresql://example")
    ledger.reserve("organization", "school-1", "image", 1, reservation_id="job-1")

    queries = "\n".join(query for query, _ in executed).lower()
    assert "for update" in queries
    assert "insert into usage_reservations values (%s, %s, %s, %s, %s)" in queries
