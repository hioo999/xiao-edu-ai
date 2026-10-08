import sys
import types
import pytest
from apps.api.app.agents.catalog import PostgresAgentCatalog
pytestmark = pytest.mark.unit
def test_postgres_agent_catalog_initializes_tools_and_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    statements=[]
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*_): return None
        def execute(self, statement, values=None):
            statements.append(statement)
        def fetchall(self): return []
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*_): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules,"psycopg",types.SimpleNamespace(connect=lambda _:Connection()))
    PostgresAgentCatalog("postgresql://example")
    assert any("runtime_managed_agents" in statement for statement in statements)
