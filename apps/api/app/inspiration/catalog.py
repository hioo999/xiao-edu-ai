from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import uuid

from .models import InspirationCase


class InspirationCatalog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._cases: dict[str, InspirationCase] = {}
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("inspiration persistence is not configured")
        return sqlite3.connect(self._storage_path)

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("create table if not exists inspiration_cases (case_id text primary key, title text not null, grade_min integer not null, grade_max integer not null, interests text not null, difficulty text not null, duration_minutes integer not null, prompt text not null, capability text not null, organization_ids text not null, attachment_id text not null default '', attachment_filename text not null default '')")
            for column in ("attachment_id text not null default ''", "attachment_filename text not null default ''"):
                try: connection.execute(f"alter table inspiration_cases add column {column}")
                except sqlite3.OperationalError: pass
            connection.execute("create table if not exists inspiration_favorites (case_id text not null, user_id text not null, organization_id text not null, primary key (case_id, user_id, organization_id))")

    def _load(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select case_id, title, grade_min, grade_max, interests, difficulty, duration_minutes, prompt, capability, organization_ids, attachment_id, attachment_filename from inspiration_cases").fetchall()
        self._cases = {
            row[0]: InspirationCase(row[0], row[1], (row[2], row[3]), set(json.loads(row[4])), row[5], row[6], set(json.loads(row[9])), row[7], row[8], row[10], row[11])
            for row in rows
        }

    def save(self, case: InspirationCase) -> InspirationCase:
        self._cases[case.case_id] = case
        if self._storage_path:
            with self._connect() as connection:
                connection.execute(
                    "insert into inspiration_cases values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict(case_id) do update set title=excluded.title, grade_min=excluded.grade_min, grade_max=excluded.grade_max, interests=excluded.interests, difficulty=excluded.difficulty, duration_minutes=excluded.duration_minutes, prompt=excluded.prompt, capability=excluded.capability, organization_ids=excluded.organization_ids, attachment_id=excluded.attachment_id, attachment_filename=excluded.attachment_filename",
                    (case.case_id, case.title, case.grade_range[0], case.grade_range[1], json.dumps(sorted(case.interests), ensure_ascii=False), case.difficulty, case.duration_minutes, case.prompt, case.capability, json.dumps(sorted(case.approved_organization_ids)), case.attachment_id, case.attachment_filename),
                )
        return case

    def create(self, *, title: str, grade_range: tuple[int, int], interests: set[str], difficulty: str, duration_minutes: int, prompt: str, capability: str, organization_ids: set[str], attachment_id: str = "", attachment_filename: str = "") -> InspirationCase:
        return self.save(InspirationCase(f"case-{uuid.uuid4().hex[:12]}", title, grade_range, interests, difficulty, duration_minutes, organization_ids, prompt, capability, attachment_id, attachment_filename))

    def list_visible(self, organization_id: str) -> list[InspirationCase]:
        return sorted((case for case in self._cases.values() if organization_id in case.approved_organization_ids), key=lambda item: item.case_id)

    def favorite(self, case_id: str, user_id: str, organization_id: str, enabled: bool) -> None:
        if case_id not in self._cases or organization_id not in self._cases[case_id].approved_organization_ids:
            raise KeyError(case_id)
        if not self._storage_path:
            return
        with self._connect() as connection:
            if enabled:
                connection.execute("insert or ignore into inspiration_favorites values (?, ?, ?)", (case_id, user_id, organization_id))
            else:
                connection.execute("delete from inspiration_favorites where case_id = ? and user_id = ? and organization_id = ?", (case_id, user_id, organization_id))

    def favorites_for(self, user_id: str, organization_id: str) -> set[str]:
        if not self._storage_path:
            return set()
        with self._connect() as connection:
            return {row[0] for row in connection.execute("select case_id from inspiration_favorites where user_id = ? and organization_id = ?", (user_id, organization_id))}

    def delete(self, case_id: str) -> None:
        if case_id not in self._cases:
            raise KeyError(case_id)
        del self._cases[case_id]
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from inspiration_cases where case_id = ?", (case_id,))
                connection.execute("delete from inspiration_favorites where case_id = ?", (case_id,))


class PostgresInspirationCatalog(InspirationCatalog):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL inspiration catalog requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_inspiration_cases (case_id text primary key, title text not null, grade_min integer not null, grade_max integer not null, interests text not null, difficulty text not null, duration_minutes integer not null, prompt text not null, capability text not null, organization_ids text not null, attachment_id text not null default '', attachment_filename text not null default '')")
            cursor.execute("alter table runtime_inspiration_cases add column if not exists attachment_id text not null default ''")
            cursor.execute("alter table runtime_inspiration_cases add column if not exists attachment_filename text not null default ''")
            cursor.execute("create table if not exists runtime_inspiration_favorites (case_id text not null, user_id text not null, organization_id text not null, primary key (case_id, user_id, organization_id))")
        self._refresh()

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)
    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select case_id, title, grade_min, grade_max, interests, difficulty, duration_minutes, prompt, capability, organization_ids, attachment_id, attachment_filename from runtime_inspiration_cases")
            rows = cursor.fetchall()
        self._cases = {str(row[0]): InspirationCase(str(row[0]), str(row[1]), (int(row[2]), int(row[3])), set(json.loads(row[4])), str(row[5]), int(row[6]), set(json.loads(row[9])), str(row[7]), str(row[8]), str(row[10]), str(row[11])) for row in rows}
    def save(self, case: InspirationCase) -> InspirationCase:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into runtime_inspiration_cases values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(case_id) do update set title=excluded.title,grade_min=excluded.grade_min,grade_max=excluded.grade_max,interests=excluded.interests,difficulty=excluded.difficulty,duration_minutes=excluded.duration_minutes,prompt=excluded.prompt,capability=excluded.capability,organization_ids=excluded.organization_ids,attachment_id=excluded.attachment_id,attachment_filename=excluded.attachment_filename""", (case.case_id, case.title, case.grade_range[0], case.grade_range[1], json.dumps(sorted(case.interests), ensure_ascii=False), case.difficulty, case.duration_minutes, case.prompt, case.capability, json.dumps(sorted(case.approved_organization_ids)), case.attachment_id, case.attachment_filename))
        self._cases[case.case_id] = case
        return case
    def list_visible(self, organization_id: str) -> list[InspirationCase]: self._refresh(); return super().list_visible(organization_id)
    def favorite(self, case_id: str, user_id: str, organization_id: str, enabled: bool) -> None:
        self._refresh()
        if case_id not in self._cases or organization_id not in self._cases[case_id].approved_organization_ids: raise KeyError(case_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            if enabled: cursor.execute("insert into runtime_inspiration_favorites values (%s,%s,%s) on conflict do nothing", (case_id, user_id, organization_id))
            else: cursor.execute("delete from runtime_inspiration_favorites where case_id = %s and user_id = %s and organization_id = %s", (case_id, user_id, organization_id))
    def favorites_for(self, user_id: str, organization_id: str) -> set[str]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select case_id from runtime_inspiration_favorites where user_id = %s and organization_id = %s", (user_id, organization_id))
            return {str(row[0]) for row in cursor.fetchall()}
