import sys
import types
import pytest
from apps.api.app.audit.service import PostgresAuditLog
pytestmark = pytest.mark.unit
def test_postgres_audit_log_uses_parameterized_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*_args): return None
        def execute(self, statement, values=None): statements.append((statement, values))
        def fetchone(self): return (1, "2026-01-01T00:00:00+00:00")
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    log = PostgresAuditLog("postgresql://example")
    log.record(organization_id="org", actor_id="user", action="recorded", target_type="target", target_id="item")
    assert any("values (%s,%s,%s,%s,%s)" in statement.lower() for statement, _values in statements)
