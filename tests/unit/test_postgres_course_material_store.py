import sys
import types
import pytest
from apps.api.app.courses.storage import PostgresCourseMaterialStore
pytestmark = pytest.mark.unit
def test_postgres_course_material_store_creates_shared_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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
    PostgresCourseMaterialStore(tmp_path, "postgresql://example")
    assert any("runtime_course_materials" in statement for statement in statements)
