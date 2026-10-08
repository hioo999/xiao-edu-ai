import sys
import types

import pytest

from apps.api.app.projects.catalog import PostgresCreativeAssetCatalog


pytestmark = pytest.mark.unit


def test_postgres_asset_catalog_uses_conflict_safe_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[tuple[str, object]] = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, query, values=None): executed.append((query, values))
        def fetchall(self): return []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: Connection()))
    catalog = PostgresCreativeAssetCatalog("postgresql://example")
    catalog.create(project_id="p-1", organization_id="o-1", owner_user_id="u-1", kind="image", title="猫", preview_url="https://example.test/cat.png", prompt="猫")
    assert any("on conflict(asset_id)" in query.lower() for query, _ in executed)
