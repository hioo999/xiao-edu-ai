import sys
import types
import pytest
from apps.api.app.settings.service import OrganizationSettings, PostgresSettingsStore
pytestmark = pytest.mark.unit
def test_postgres_settings_store_uses_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement, values=None): statements.append(statement)
        def fetchone(self): return None
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    store = PostgresSettingsStore("postgresql://example")
    store.save(OrganizationSettings("org-1"))
    assert any("on conflict(organization_id)" in statement.lower() for statement in statements)
