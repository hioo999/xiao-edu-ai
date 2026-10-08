from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import sqlite3


class ModerationDecision(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ModerationPolicy:
    enabled: bool = True
    modes: tuple[str, ...] = ("classroom", "free_creation")
    blocked_terms: tuple[str, ...] = ()


class ModerationPolicyStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    "create table if not exists moderation_policy "
                    "(id integer primary key check (id = 1), enabled integer not null default 1, blocked_terms text not null default '')"
                )

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("moderation policy persistence is not configured")
        return sqlite3.connect(self._storage_path)

    def get(self) -> ModerationPolicy:
        if not self._storage_path:
            return ModerationPolicy()
        with self._connect() as connection:
            row = connection.execute("select enabled, blocked_terms from moderation_policy where id = 1").fetchone()
        if row is None:
            return ModerationPolicy()
        terms = tuple(term.strip() for term in row[1].split("\n") if term.strip())
        return ModerationPolicy(enabled=bool(row[0]), blocked_terms=terms)

    def save(self, policy: ModerationPolicy) -> ModerationPolicy:
        if self._storage_path:
            joined = "\n".join(policy.blocked_terms)
            with self._connect() as connection:
                connection.execute(
                    "insert into moderation_policy (id, enabled, blocked_terms) values (1, ?, ?) "
                    "on conflict(id) do update set enabled=excluded.enabled, blocked_terms=excluded.blocked_terms",
                    (int(policy.enabled), joined),
                )
        return policy


class ModerationService:
    def __init__(
        self,
        blocked_terms: set[str] | None = None,
        *,
        store: ModerationPolicyStore | None = None,
        enabled: bool = True,
    ) -> None:
        self._memory_terms = {term.strip() for term in (blocked_terms or set()) if term.strip()}
        self._store = store
        self._enabled = enabled
        self._modes = ("classroom", "free_creation")

    def policy(self) -> ModerationPolicy:
        if self._store:
            stored = self._store.get()
            merged_terms = set(stored.blocked_terms) | self._memory_terms
            return ModerationPolicy(enabled=stored.enabled, modes=self._modes, blocked_terms=tuple(sorted(merged_terms)))
        return ModerationPolicy(enabled=self._enabled, modes=self._modes, blocked_terms=tuple(sorted(self._memory_terms)))

    def update_policy(self, *, enabled: bool, blocked_terms: list[str]) -> ModerationPolicy:
        normalized = tuple(sorted({term.strip() for term in blocked_terms if term.strip()}))
        self._enabled = enabled
        self._memory_terms = set(normalized)
        if self._store:
            self._store.save(ModerationPolicy(enabled=enabled, blocked_terms=normalized))
        return ModerationPolicy(enabled=enabled, modes=self._modes, blocked_terms=normalized)

    def check(self, content: str, *, mode: str) -> ModerationDecision:
        if not self.policy().enabled:
            return ModerationDecision.ALLOWED
        if any(term in content for term in self.policy().blocked_terms):
            return ModerationDecision.BLOCKED
        return ModerationDecision.ALLOWED
