from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class OrganizationSettings:
    organization_id: str
    display_name: str = "星芽 AI 创作学习平台"
    student_home_enabled: bool = True
    maintenance_message: str = ""
    showcase_columns: int = 4
    showcase_rows: int = 2
    showcase_sort: str = "featured"
    showcase_kind: str = "all"


class SettingsStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._settings: dict[str, OrganizationSettings] = {}
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute("create table if not exists organization_settings (organization_id text primary key, display_name text not null, student_home_enabled integer not null, maintenance_message text not null)")
                columns = {row[1] for row in connection.execute("pragma table_info(organization_settings)")}
                for name, definition in (("showcase_columns", "integer not null default 4"), ("showcase_rows", "integer not null default 2"), ("showcase_sort", "text not null default 'featured'"), ("showcase_kind", "text not null default 'all'")):
                    if name not in columns:
                        connection.execute(f"alter table organization_settings add column {name} {definition}")
            self._load()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("settings persistence is not configured")
        return sqlite3.connect(self._storage_path)

    def _load(self) -> None:
        with self._connect() as connection:
            for row in connection.execute("select organization_id, display_name, student_home_enabled, maintenance_message, showcase_columns, showcase_rows, showcase_sort, showcase_kind from organization_settings"):
                self._settings[row[0]] = OrganizationSettings(row[0], row[1], bool(row[2]), row[3], row[4], row[5], row[6], row[7])

    def get(self, organization_id: str) -> OrganizationSettings:
        return self._settings.get(organization_id, OrganizationSettings(organization_id))

    def save(self, settings: OrganizationSettings) -> OrganizationSettings:
        self._settings[settings.organization_id] = settings
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into organization_settings (organization_id, display_name, student_home_enabled, maintenance_message, showcase_columns, showcase_rows, showcase_sort, showcase_kind) values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(organization_id) do update set display_name=excluded.display_name, student_home_enabled=excluded.student_home_enabled, maintenance_message=excluded.maintenance_message, showcase_columns=excluded.showcase_columns, showcase_rows=excluded.showcase_rows, showcase_sort=excluded.showcase_sort, showcase_kind=excluded.showcase_kind", (settings.organization_id, settings.display_name, int(settings.student_home_enabled), settings.maintenance_message, settings.showcase_columns, settings.showcase_rows, settings.showcase_sort, settings.showcase_kind))
        return settings


class PostgresSettingsStore(SettingsStore):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL settings store requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_organization_settings (organization_id text primary key, display_name text not null, student_home_enabled boolean not null, maintenance_message text not null, showcase_columns integer not null, showcase_rows integer not null, showcase_sort text not null, showcase_kind text not null)")

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)

    def get(self, organization_id: str) -> OrganizationSettings:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select organization_id, display_name, student_home_enabled, maintenance_message, showcase_columns, showcase_rows, showcase_sort, showcase_kind from runtime_organization_settings where organization_id = %s", (organization_id,))
            row = cursor.fetchone()
        return OrganizationSettings(*row) if row else OrganizationSettings(organization_id)

    def save(self, settings: OrganizationSettings) -> OrganizationSettings:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into runtime_organization_settings values (%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(organization_id) do update set display_name=excluded.display_name,student_home_enabled=excluded.student_home_enabled,maintenance_message=excluded.maintenance_message,showcase_columns=excluded.showcase_columns,showcase_rows=excluded.showcase_rows,showcase_sort=excluded.showcase_sort,showcase_kind=excluded.showcase_kind""", (settings.organization_id, settings.display_name, settings.student_home_enabled, settings.maintenance_message, settings.showcase_columns, settings.showcase_rows, settings.showcase_sort, settings.showcase_kind))
        return settings
