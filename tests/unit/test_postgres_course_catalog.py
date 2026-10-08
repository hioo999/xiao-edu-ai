import sys
import types

import pytest

from apps.api.app.courses.catalog import PostgresCourseCatalog


pytestmark = pytest.mark.unit


def test_postgres_course_catalog_initializes_shared_publication_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement, values=None): statements.append((statement, values))
        def fetchall(self): return []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    PostgresCourseCatalog("postgresql://example")
    assert any("runtime_course_classrooms" in statement for statement, _ in statements)
