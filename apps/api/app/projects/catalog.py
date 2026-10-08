from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import sqlite3
import uuid

from .assets import AssetKind


@dataclass(frozen=True)
class CreativeAsset:
    asset_id: str
    project_id: str
    organization_id: str
    owner_user_id: str
    kind: AssetKind
    title: str
    preview_url: str
    prompt: str
    review_state: str = "pending"
    featured: bool = False
    cover_url: str = ""
    process_steps: tuple[str, ...] = ()
    grade_min: int = 3
    grade_max: int = 6
    visibility: str = "organization"
    is_example: bool = False


class CreativeAssetCatalog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._assets: dict[str, CreativeAsset] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("asset persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("""create table if not exists creative_assets (
                asset_id text primary key, project_id text not null, organization_id text not null,
                owner_user_id text not null, kind text not null, title text not null, preview_url text not null,
                prompt text not null, review_state text not null, featured integer not null,
                cover_url text not null default '', process_steps text not null default '[]',
                grade_min integer not null default 3, grade_max integer not null default 6,
                visibility text not null default 'organization', is_example integer not null default 0
            )""")
            columns = {row[1] for row in connection.execute("pragma table_info(creative_assets)")}
            migrations = {
                "cover_url": "alter table creative_assets add column cover_url text not null default ''",
                "process_steps": "alter table creative_assets add column process_steps text not null default '[]'",
                "grade_min": "alter table creative_assets add column grade_min integer not null default 3",
                "grade_max": "alter table creative_assets add column grade_max integer not null default 6",
                "visibility": "alter table creative_assets add column visibility text not null default 'organization'",
                "is_example": "alter table creative_assets add column is_example integer not null default 0",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

    def _load_storage(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select * from creative_assets").fetchall()
        for row in rows:
            try:
                process_steps = tuple(str(step) for step in json.loads(row["process_steps"]) if str(step).strip())
            except (TypeError, json.JSONDecodeError):
                process_steps = ()
            self._assets[row["asset_id"]] = CreativeAsset(
                row["asset_id"], row["project_id"], row["organization_id"], row["owner_user_id"], row["kind"],
                row["title"], row["preview_url"], row["prompt"], row["review_state"], bool(row["featured"]),
                row["cover_url"], process_steps, row["grade_min"], row["grade_max"], row["visibility"], bool(row["is_example"]),
            )

    def _persist(self, asset: CreativeAsset) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("""insert into creative_assets (
                    asset_id, project_id, organization_id, owner_user_id, kind, title, preview_url, prompt,
                    review_state, featured, cover_url, process_steps, grade_min, grade_max, visibility, is_example
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(asset_id) do update set
                    title=excluded.title, preview_url=excluded.preview_url, prompt=excluded.prompt,
                    review_state=excluded.review_state, featured=excluded.featured, cover_url=excluded.cover_url,
                    process_steps=excluded.process_steps, grade_min=excluded.grade_min, grade_max=excluded.grade_max,
                    visibility=excluded.visibility, is_example=excluded.is_example""", (
                    asset.asset_id, asset.project_id, asset.organization_id, asset.owner_user_id, asset.kind,
                    asset.title, asset.preview_url, asset.prompt, asset.review_state, int(asset.featured),
                    asset.cover_url, json.dumps(asset.process_steps, ensure_ascii=False), asset.grade_min,
                    asset.grade_max, asset.visibility, int(asset.is_example),
                ))

    def create(self, *, project_id: str, organization_id: str, owner_user_id: str, kind: AssetKind, title: str, preview_url: str, prompt: str, cover_url: str = "", process_steps: tuple[str, ...] = (), grade_min: int = 3, grade_max: int = 6, visibility: str = "organization", is_example: bool = False) -> CreativeAsset:
        asset = CreativeAsset(f"asset-{uuid.uuid4().hex[:12]}", project_id, organization_id, owner_user_id, kind, title, preview_url, prompt, cover_url=cover_url, process_steps=process_steps, grade_min=grade_min, grade_max=grade_max, visibility=visibility, is_example=is_example)
        self._assets[asset.asset_id] = asset
        self._persist(asset)
        return asset

    def get(self, asset_id: str, organization_id: str) -> CreativeAsset:
        asset = self._assets.get(asset_id)
        if asset is None or asset.organization_id != organization_id:
            raise KeyError(asset_id)
        return asset

    def list_for_owner(self, owner_user_id: str, organization_id: str) -> list[CreativeAsset]:
        return [asset for asset in self._assets.values() if asset.owner_user_id == owner_user_id and asset.organization_id == organization_id]

    def list_for_review(self, organization_id: str, *, kind: str | None = None, review_state: str | None = None, featured: bool | None = None, search: str | None = None) -> list[CreativeAsset]:
        normalized_search = search.strip().lower() if search else None
        assets = []
        for asset in self._assets.values():
            if asset.organization_id != organization_id:
                continue
            if kind and asset.kind != kind:
                continue
            if review_state and asset.review_state != review_state:
                continue
            if featured is not None and asset.featured != featured:
                continue
            if normalized_search and normalized_search not in asset.title.lower() and normalized_search not in asset.owner_user_id.lower():
                continue
            assets.append(asset)
        return sorted(assets, key=lambda asset: asset.asset_id, reverse=True)

    def list_showcase(self, organization_id: str, *, kind: str | None = None, limit: int = 24, sort: str = "featured") -> list[CreativeAsset]:
        assets = [asset for asset in self._assets.values() if asset.organization_id == organization_id and asset.review_state == "approved" and (kind is None or kind == "all" or asset.kind == kind)]
        if sort == "newest":
            assets.sort(key=lambda asset: asset.asset_id, reverse=True)
        else:
            assets.sort(key=lambda asset: (not asset.featured, asset.asset_id), reverse=False)
        return assets[:limit]

    def review(self, asset_id: str, organization_id: str, state: str, featured: bool) -> CreativeAsset:
        asset = self.get(asset_id, organization_id)
        reviewed = replace(asset, review_state=state, featured=featured)
        self._assets[asset_id] = reviewed
        self._persist(reviewed)
        return reviewed

    def update_metadata(self, asset_id: str, organization_id: str, *, title: str | None = None, preview_url: str | None = None, cover_url: str | None = None, process_steps: tuple[str, ...] | None = None, grade_min: int | None = None, grade_max: int | None = None, visibility: str | None = None, is_example: bool | None = None) -> CreativeAsset:
        asset = self.get(asset_id, organization_id)
        updated = replace(
            asset,
            title=title if title is not None else asset.title,
            preview_url=preview_url if preview_url is not None else asset.preview_url,
            cover_url=cover_url if cover_url is not None else asset.cover_url,
            process_steps=process_steps if process_steps is not None else asset.process_steps,
            grade_min=grade_min if grade_min is not None else asset.grade_min,
            grade_max=grade_max if grade_max is not None else asset.grade_max,
            visibility=visibility if visibility is not None else asset.visibility,
            is_example=is_example if is_example is not None else asset.is_example,
        )
        self._assets[asset_id] = updated
        self._persist(updated)
        return updated

    def delete(self, asset_id: str, organization_id: str) -> None:
        self.get(asset_id, organization_id)
        del self._assets[asset_id]
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from creative_assets where asset_id = ?", (asset_id,))


class PostgresCreativeAssetCatalog(CreativeAssetCatalog):
    """Shared artwork catalog for API instances and generation workers."""

    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL asset catalog requires psycopg") from exc
        self._psycopg = psycopg
        self._database_url = database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""create table if not exists runtime_creative_assets (
                asset_id text primary key, project_id text not null, organization_id text not null,
                owner_user_id text not null, kind text not null, title text not null, preview_url text not null,
                prompt text not null, review_state text not null, featured boolean not null,
                cover_url text not null default '', process_steps jsonb not null default '[]'::jsonb,
                grade_min integer not null default 3, grade_max integer not null default 6,
                visibility text not null default 'organization', is_example boolean not null default false)""")
            cursor.execute("alter table runtime_creative_assets add column if not exists cover_url text not null default ''")
            cursor.execute("alter table runtime_creative_assets add column if not exists process_steps jsonb not null default '[]'::jsonb")
            cursor.execute("alter table runtime_creative_assets add column if not exists grade_min integer not null default 3")
            cursor.execute("alter table runtime_creative_assets add column if not exists grade_max integer not null default 6")
            cursor.execute("alter table runtime_creative_assets add column if not exists visibility text not null default 'organization'")
            cursor.execute("alter table runtime_creative_assets add column if not exists is_example boolean not null default false")
        self._refresh()

    def _connect_postgres(self):
        return self._psycopg.connect(self._database_url)

    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select asset_id, project_id, organization_id, owner_user_id, kind, title, preview_url, prompt, review_state, featured, cover_url, process_steps, grade_min, grade_max, visibility, is_example from runtime_creative_assets")
            rows = cursor.fetchall()
        self._assets = {str(row[0]): CreativeAsset(str(row[0]), str(row[1]), str(row[2]), str(row[3]), row[4], str(row[5]), str(row[6]), str(row[7]), str(row[8]), bool(row[9]), str(row[10]), tuple(str(step) for step in row[11]), int(row[12]), int(row[13]), str(row[14]), bool(row[15])) for row in rows}

    def _persist(self, asset: CreativeAsset) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into runtime_creative_assets values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                on conflict(asset_id) do update set title=excluded.title, preview_url=excluded.preview_url,
                prompt=excluded.prompt, review_state=excluded.review_state, featured=excluded.featured,
                cover_url=excluded.cover_url, process_steps=excluded.process_steps, grade_min=excluded.grade_min,
                grade_max=excluded.grade_max, visibility=excluded.visibility, is_example=excluded.is_example""", (asset.asset_id, asset.project_id, asset.organization_id, asset.owner_user_id, asset.kind, asset.title, asset.preview_url, asset.prompt, asset.review_state, asset.featured, asset.cover_url, json.dumps(asset.process_steps), asset.grade_min, asset.grade_max, asset.visibility, asset.is_example))

    def get(self, asset_id: str, organization_id: str) -> CreativeAsset:
        self._refresh()
        return super().get(asset_id, organization_id)

    def list_for_owner(self, owner_user_id: str, organization_id: str) -> list[CreativeAsset]:
        self._refresh()
        return super().list_for_owner(owner_user_id, organization_id)

    def list_for_review(self, organization_id: str, **kwargs) -> list[CreativeAsset]:
        self._refresh()
        return super().list_for_review(organization_id, **kwargs)

    def list_showcase(self, organization_id: str, **kwargs) -> list[CreativeAsset]:
        self._refresh()
        return super().list_showcase(organization_id, **kwargs)

    def delete(self, asset_id: str, organization_id: str) -> None:
        self.get(asset_id, organization_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_creative_assets where asset_id = %s", (asset_id,))
        self._assets.pop(asset_id, None)
