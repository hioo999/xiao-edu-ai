import sys
import types
import pytest
from apps.api.app.classrooms.assistance import PostgresAssistanceManager
pytestmark = pytest.mark.unit
def test_postgres_classroom_manager_initializes_live_state_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement, values=None): statements.append(statement)
        def fetchall(self): return []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    PostgresAssistanceManager("postgresql://example")
    assert any("runtime_student_presence" in statement for statement in statements)
