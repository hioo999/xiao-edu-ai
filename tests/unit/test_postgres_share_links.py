import sys
import types
import pytest
from apps.api.app.sharing.links import PostgresShareLinkService
pytestmark = pytest.mark.unit
def test_postgres_share_links_use_conflict_safe_revoke(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement, values=None): statements.append(statement)
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    PostgresShareLinkService("postgresql://example")
    assert any("runtime_share_links" in statement for statement in statements)
