from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class AuditRecord:
    record_id: int
    organization_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    created_at: str


class AuditLog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("create table if not exists audit_records (record_id integer primary key autoincrement, organization_id text not null, actor_id text not null, action text not null, target_type text not null, target_id text not null, created_at text not null)")
            self._load()

    def _load(self) -> None:
        if not self._storage_path:
            return
        with sqlite3.connect(self._storage_path) as connection:
            self._records = [AuditRecord(*row) for row in connection.execute("select record_id, organization_id, actor_id, action, target_type, target_id, created_at from audit_records order by record_id desc")]

    def record(self, *, organization_id: str, actor_id: str, action: str, target_type: str, target_id: str) -> AuditRecord:
        created_at = datetime.now(timezone.utc).isoformat()
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                cursor = connection.execute("insert into audit_records (organization_id, actor_id, action, target_type, target_id, created_at) values (?, ?, ?, ?, ?, ?)", (organization_id, actor_id, action, target_type, target_id, created_at))
                record = AuditRecord(cursor.lastrowid, organization_id, actor_id, action, target_type, target_id, created_at)
        else:
            record = AuditRecord(len(self._records) + 1, organization_id, actor_id, action, target_type, target_id, created_at)
        self._records.insert(0, record)
        return record

    def list_for_organization(self, organization_id: str, *, limit: int = 100, offset: int = 0, actor_id: str | None = None, action: str | None = None, target_type: str | None = None, since: str | None = None, until: str | None = None) -> list[AuditRecord]:
        records = [record for record in self._records if record.organization_id == organization_id]
        if actor_id:
            records = [record for record in records if record.actor_id == actor_id]
        if action:
            records = [record for record in records if record.action == action]
        if target_type:
            records = [record for record in records if record.target_type == target_type]
        if since:
            records = [record for record in records if record.created_at >= since]
        if until:
            records = [record for record in records if record.created_at <= until]
        return records[offset:offset + limit]


class PostgresAuditLog(AuditLog):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL audit log requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_audit_records (record_id bigint generated always as identity primary key, organization_id text not null, actor_id text not null, action text not null, target_type text not null, target_id text not null, created_at timestamptz not null default now())")
            cursor.execute("create index if not exists runtime_audit_organization_idx on runtime_audit_records (organization_id, created_at desc)")

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)
    def record(self, *, organization_id: str, actor_id: str, action: str, target_type: str, target_id: str) -> AuditRecord:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_audit_records (organization_id, actor_id, action, target_type, target_id) values (%s,%s,%s,%s,%s) returning record_id, created_at::text", (organization_id, actor_id, action, target_type, target_id))
            row = cursor.fetchone()
        return AuditRecord(int(row[0]), organization_id, actor_id, action, target_type, target_id, str(row[1]))
    def list_for_organization(self, organization_id: str, *, limit: int = 100, offset: int = 0, actor_id: str | None = None, action: str | None = None, target_type: str | None = None, since: str | None = None, until: str | None = None) -> list[AuditRecord]:
        clauses, values = ["organization_id = %s"], [organization_id]
        for column, value in (("actor_id", actor_id), ("action", action), ("target_type", target_type)):
            if value: clauses.append(f"{column} = %s"); values.append(value)
        if since: clauses.append("created_at >= %s"); values.append(since)
        if until: clauses.append("created_at <= %s"); values.append(until)
        values.extend([limit, offset])
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute(f"select record_id, organization_id, actor_id, action, target_type, target_id, created_at::text from runtime_audit_records where {' and '.join(clauses)} order by record_id desc limit %s offset %s", values)
            return [AuditRecord(*row) for row in cursor.fetchall()]
