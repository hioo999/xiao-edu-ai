from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class ModelCall:
    organization_id: str
    provider_id: str
    capability: str
    outcome: str
    created_at: str


class ModelCallLog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._calls: list[ModelCall] = []
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("create table if not exists model_calls (organization_id text not null, provider_id text not null, capability text not null, outcome text not null, created_at text not null)")

    def record(self, organization_id: str, provider_id: str, capability: str, outcome: str) -> None:
        call = ModelCall(organization_id, provider_id, capability, outcome, datetime.now(timezone.utc).isoformat())
        self._calls.append(call)
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("insert into model_calls values (?, ?, ?, ?, ?)", (call.organization_id, call.provider_id, call.capability, call.outcome, call.created_at))

    def summary(self, organization_id: str) -> list[dict[str, object]]:
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                rows = connection.execute("select provider_id, capability, outcome, count(*) from model_calls where organization_id = ? group by provider_id, capability, outcome", (organization_id,)).fetchall()
            return [{"providerId": row[0], "capability": row[1], "outcome": row[2], "count": row[3]} for row in rows]
        grouped: dict[tuple[str, str, str], int] = {}
        for call in self._calls:
            if call.organization_id == organization_id:
                key = (call.provider_id, call.capability, call.outcome)
                grouped[key] = grouped.get(key, 0) + 1
        return [{"providerId": key[0], "capability": key[1], "outcome": key[2], "count": count} for key, count in grouped.items()]

    def recent(self, organization_id: str, *, limit: int = 100, offset: int = 0, provider_id: str | None = None, capability: str | None = None, outcome: str | None = None) -> list[ModelCall]:
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                clauses = ["organization_id = ?"]
                values: list[object] = [organization_id]
                for field, value in (("provider_id", provider_id), ("capability", capability), ("outcome", outcome)):
                    if value:
                        clauses.append(f"{field} = ?")
                        values.append(value)
                values.extend([limit, offset])
                rows = connection.execute(f"select organization_id, provider_id, capability, outcome, created_at from model_calls where {' and '.join(clauses)} order by created_at desc limit ? offset ?", values).fetchall()
            return [ModelCall(*row) for row in rows]
        calls = [call for call in reversed(self._calls) if call.organization_id == organization_id and (not provider_id or call.provider_id == provider_id) and (not capability or call.capability == capability) and (not outcome or call.outcome == outcome)]
        return calls[offset:offset + limit]


class PostgresModelCallLog:
    """PostgreSQL implementation for high-volume model call observability."""

    def __init__(self, database_url: str) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL model call logging requires psycopg") from exc
        self._psycopg = psycopg
        self._database_url = database_url
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists model_calls (organization_id text not null, provider_id text not null, capability text not null, outcome text not null, created_at timestamptz not null)")
            cursor.execute("create index if not exists model_calls_organization_created_idx on model_calls (organization_id, created_at desc)")

    def _connect(self):
        return self._psycopg.connect(self._database_url)

    def record(self, organization_id: str, provider_id: str, capability: str, outcome: str) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("insert into model_calls (organization_id, provider_id, capability, outcome, created_at) values (%s, %s, %s, %s, now())", (organization_id, provider_id, capability, outcome))

    def summary(self, organization_id: str) -> list[dict[str, object]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select provider_id, capability, outcome, count(*) from model_calls where organization_id = %s group by provider_id, capability, outcome", (organization_id,))
            return [{"providerId": row[0], "capability": row[1], "outcome": row[2], "count": row[3]} for row in cursor.fetchall()]

    def recent(self, organization_id: str, *, limit: int = 100, offset: int = 0, provider_id: str | None = None, capability: str | None = None, outcome: str | None = None) -> list[ModelCall]:
        clauses = ["organization_id = %s"]
        values: list[object] = [organization_id]
        for field, value in (("provider_id", provider_id), ("capability", capability), ("outcome", outcome)):
            if value:
                clauses.append(f"{field} = %s")
                values.append(value)
        values.extend([limit, offset])
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"select organization_id, provider_id, capability, outcome, created_at::text from model_calls where {' and '.join(clauses)} order by created_at desc limit %s offset %s", values)
            return [ModelCall(*row) for row in cursor.fetchall()]
