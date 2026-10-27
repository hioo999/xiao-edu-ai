from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


class QuotaExceeded(PermissionError):
    pass


@dataclass(frozen=True)
class Reservation:
    scope: str
    scope_id: str
    metric: str
    amount: int


class UsageLedger:
    def __init__(self, limits: dict[tuple[str, str, str], int], storage_path: str | Path | None = None) -> None:
        self._limits = limits
        self._committed: dict[tuple[str, str, str], int] = {}
        self._reserved: dict[tuple[str, str, str], int] = {}
        self._reservations: dict[str, Reservation] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("usage persistence is not configured")
        return sqlite3.connect(self._storage_path)

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("create table if not exists usage_limits (scope text, scope_id text, metric text, amount integer not null, primary key (scope, scope_id, metric))")
            connection.execute("create table if not exists usage_committed (scope text, scope_id text, metric text, amount integer not null, primary key (scope, scope_id, metric))")
            connection.execute("create table if not exists usage_reservations (reservation_id text primary key, scope text not null, scope_id text not null, metric text not null, amount integer not null)")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            for scope, scope_id, metric, amount in connection.execute("select scope, scope_id, metric, amount from usage_limits"):
                self._limits[(scope, scope_id, metric)] = amount
            for scope, scope_id, metric, amount in connection.execute("select scope, scope_id, metric, amount from usage_committed"):
                self._committed[(scope, scope_id, metric)] = amount
            for reservation_id, scope, scope_id, metric, amount in connection.execute("select reservation_id, scope, scope_id, metric, amount from usage_reservations"):
                reservation = Reservation(scope, scope_id, metric, amount)
                self._reservations[reservation_id] = reservation
                key = (scope, scope_id, metric)
                self._reserved[key] = self._reserved.get(key, 0) + amount

    def _persist_limit(self, key: tuple[str, str, str]) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into usage_limits values (?, ?, ?, ?) on conflict(scope, scope_id, metric) do update set amount=excluded.amount", (*key, self._limits[key]))

    def _persist_committed(self, key: tuple[str, str, str]) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into usage_committed values (?, ?, ?, ?) on conflict(scope, scope_id, metric) do update set amount=excluded.amount", (*key, self._committed.get(key, 0)))

    def set_limit(self, scope: str, scope_id: str, metric: str, amount: int) -> None:
        if amount < 0:
            raise ValueError("limit cannot be negative")
        key = (scope, scope_id, metric)
        self._limits[key] = amount
        self._persist_limit(key)

    def grant(self, scope: str, scope_id: str, metric: str, amount: int) -> None:
        if amount <= 0:
            raise ValueError("grant must be positive")
        key = (scope, scope_id, metric)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("begin immediate")
                connection.execute("insert into usage_limits values (?, ?, ?, ?) on conflict(scope, scope_id, metric) do update set amount = usage_limits.amount + excluded.amount", (*key, amount))
            return
        self._limits[key] = self._limits.get(key, 0) + amount

    def is_configured(self, scope: str, scope_id: str, metric: str) -> bool:
        if self._storage_path:
            with self._connect() as connection:
                return connection.execute("select 1 from usage_limits where scope = ? and scope_id = ? and metric = ?", (scope, scope_id, metric)).fetchone() is not None
        return (scope, scope_id, metric) in self._limits

    def configured_scope(self, scopes: list[tuple[str, str]], metric: str) -> tuple[str, str] | None:
        return next((scope for scope in scopes if self.is_configured(scope[0], scope[1], metric)), None)

    def reserve_with_fallback(self, scopes: list[tuple[str, str]], metric: str, amount: int, *, reservation_id: str) -> tuple[str, str] | None:
        selected = self.configured_scope(scopes, metric)
        if selected is None:
            return None
        self.reserve(selected[0], selected[1], metric, amount, reservation_id=reservation_id)
        return selected

    def summary(self, scope: str, scope_id: str) -> list[dict[str, int | str]]:
        if self._storage_path:
            with self._connect() as connection:
                rows = connection.execute("""select limits.metric, limits.amount, coalesce(committed.amount, 0), coalesce(reserved.amount, 0)
                    from usage_limits limits
                    left join usage_committed committed on (committed.scope, committed.scope_id, committed.metric) = (limits.scope, limits.scope_id, limits.metric)
                    left join (select scope, scope_id, metric, sum(amount) as amount from usage_reservations group by scope, scope_id, metric) reserved on (reserved.scope, reserved.scope_id, reserved.metric) = (limits.scope, limits.scope_id, limits.metric)
                    where limits.scope = ? and limits.scope_id = ? order by limits.metric""", (scope, scope_id)).fetchall()
            return [{"metric": row[0], "limit": row[1], "used": row[2], "reserved": row[3]} for row in rows]
        metrics = sorted(metric for current_scope, current_id, metric in self._limits if current_scope == scope and current_id == scope_id)
        return [{"metric": metric, "limit": self._limits[(scope, scope_id, metric)], "used": self._committed.get((scope, scope_id, metric), 0), "reserved": self._reserved.get((scope, scope_id, metric), 0)} for metric in metrics]

    def reserve(
        self,
        scope: str,
        scope_id: str,
        metric: str,
        amount: int,
        *,
        reservation_id: str,
    ) -> None:
        if amount < 1:
            raise ValueError("amount must be positive")
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("begin immediate")
                existing = connection.execute("select scope, scope_id, metric, amount from usage_reservations where reservation_id = ?", (reservation_id,)).fetchone()
                if existing:
                    if Reservation(*existing) != Reservation(scope, scope_id, metric, amount):
                        raise ValueError("reservation id already belongs to another usage")
                    return
                limit = connection.execute("select amount from usage_limits where scope = ? and scope_id = ? and metric = ?", (scope, scope_id, metric)).fetchone()
                if limit is None:
                    raise QuotaExceeded("quota is not configured")
                committed = connection.execute("select coalesce(amount, 0) from usage_committed where scope = ? and scope_id = ? and metric = ?", (scope, scope_id, metric)).fetchone()
                reserved = connection.execute("select coalesce(sum(amount), 0) from usage_reservations where scope = ? and scope_id = ? and metric = ?", (scope, scope_id, metric)).fetchone()[0]
                if (committed[0] if committed else 0) + reserved + amount > limit[0]:
                    raise QuotaExceeded("quota exceeded")
                connection.execute("insert into usage_reservations values (?, ?, ?, ?, ?)", (reservation_id, scope, scope_id, metric, amount))
            return
        existing = self._reservations.get(reservation_id)
        if existing is not None:
            if existing != Reservation(scope, scope_id, metric, amount):
                raise ValueError("reservation id already belongs to another usage")
            return
        key = (scope, scope_id, metric)
        limit = self._limits.get(key)
        if limit is None:
            raise QuotaExceeded("quota is not configured")
        current = self._committed.get(key, 0) + self._reserved.get(key, 0)
        if current + amount > limit:
            raise QuotaExceeded("quota exceeded")
        self._reserved[key] = self._reserved.get(key, 0) + amount
        self._reservations[reservation_id] = Reservation(scope, scope_id, metric, amount)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into usage_reservations values (?, ?, ?, ?, ?)", (reservation_id, scope, scope_id, metric, amount))

    def finalize(self, reservation_id: str) -> None:
        self.finalize_amount(reservation_id)

    def finalize_amount(self, reservation_id: str, amount: int | None = None) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("begin immediate")
                row = connection.execute("select scope, scope_id, metric, amount from usage_reservations where reservation_id = ?", (reservation_id,)).fetchone()
                if row is None:
                    return
                charge = row[3] if amount is None else amount
                if charge < 0 or charge > row[3]:
                    raise ValueError("charge exceeds reserved amount")
                connection.execute("insert into usage_committed values (?, ?, ?, ?) on conflict(scope, scope_id, metric) do update set amount = usage_committed.amount + excluded.amount", (row[0], row[1], row[2], charge))
                connection.execute("delete from usage_reservations where reservation_id = ?", (reservation_id,))
            return
        reservation = self._reservations.pop(reservation_id, None)
        if reservation is None:
            return
        charge = reservation.amount if amount is None else amount
        if charge < 0 or charge > reservation.amount:
            self._reservations[reservation_id] = reservation
            raise ValueError("charge exceeds reserved amount")
        key = (reservation.scope, reservation.scope_id, reservation.metric)
        self._reserved[key] -= reservation.amount
        self._committed[key] = self._committed.get(key, 0) + charge

    def release(self, reservation_id: str) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from usage_reservations where reservation_id = ?", (reservation_id,))
            return
        reservation = self._reservations.pop(reservation_id, None)
        if reservation is None:
            return
        key = (reservation.scope, reservation.scope_id, reservation.metric)
        self._reserved[key] -= reservation.amount
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from usage_reservations where reservation_id = ?", (reservation_id,))

    def committed(self, scope: str, scope_id: str, metric: str) -> int:
        if self._storage_path:
            with self._connect() as connection:
                row = connection.execute("select amount from usage_committed where scope = ? and scope_id = ? and metric = ?", (scope, scope_id, metric)).fetchone()
            return row[0] if row else 0
        return self._committed.get((scope, scope_id, metric), 0)


class PostgresUsageLedger(UsageLedger):
    """Transactional quota ledger shared by API and media-worker instances."""

    def __init__(self, database_url: str) -> None:
        self._limits = {}
        self._committed = {}
        self._reserved = {}
        self._reservations = {}
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL usage ledger requires psycopg") from exc
        self._psycopg = psycopg
        self._database_url = database_url
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists usage_limits (scope text, scope_id text, metric text, amount integer not null, primary key (scope, scope_id, metric))")
            cursor.execute("create table if not exists usage_committed (scope text, scope_id text, metric text, amount integer not null, primary key (scope, scope_id, metric))")
            cursor.execute("create table if not exists usage_reservations (reservation_id text primary key, scope text not null, scope_id text not null, metric text not null, amount integer not null)")

    def _connect(self):
        return self._psycopg.connect(self._database_url)

    def set_limit(self, scope: str, scope_id: str, metric: str, amount: int) -> None:
        if amount < 0:
            raise ValueError("limit cannot be negative")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("insert into usage_limits values (%s, %s, %s, %s) on conflict(scope, scope_id, metric) do update set amount=excluded.amount", (scope, scope_id, metric, amount))

    def grant(self, scope: str, scope_id: str, metric: str, amount: int) -> None:
        if amount <= 0:
            raise ValueError("grant must be positive")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("insert into usage_limits values (%s, %s, %s, %s) on conflict(scope, scope_id, metric) do update set amount=usage_limits.amount + excluded.amount", (scope, scope_id, metric, amount))

    def is_configured(self, scope: str, scope_id: str, metric: str) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select 1 from usage_limits where scope = %s and scope_id = %s and metric = %s", (scope, scope_id, metric))
            return cursor.fetchone() is not None

    def summary(self, scope: str, scope_id: str) -> list[dict[str, int | str]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""select limits.metric, limits.amount, coalesce(committed.amount, 0), coalesce(reserved.amount, 0)
                from usage_limits limits
                left join usage_committed committed on (committed.scope, committed.scope_id, committed.metric) = (limits.scope, limits.scope_id, limits.metric)
                left join (select scope, scope_id, metric, sum(amount) as amount from usage_reservations group by scope, scope_id, metric) reserved on (reserved.scope, reserved.scope_id, reserved.metric) = (limits.scope, limits.scope_id, limits.metric)
                where limits.scope = %s and limits.scope_id = %s order by limits.metric""", (scope, scope_id))
            rows = cursor.fetchall()
        return [{"metric": row[0], "limit": row[1], "used": row[2], "reserved": row[3]} for row in rows]

    def reserve(self, scope: str, scope_id: str, metric: str, amount: int, *, reservation_id: str) -> None:
        if amount < 1:
            raise ValueError("amount must be positive")
        requested = Reservation(scope, scope_id, metric, amount)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select scope, scope_id, metric, amount from usage_reservations where reservation_id = %s", (reservation_id,))
            existing = cursor.fetchone()
            if existing is not None:
                if Reservation(*existing) != requested:
                    raise ValueError("reservation id already belongs to another usage")
                return
            cursor.execute("select amount from usage_limits where scope = %s and scope_id = %s and metric = %s for update", (scope, scope_id, metric))
            limit_row = cursor.fetchone()
            if limit_row is None:
                raise QuotaExceeded("quota is not configured")
            cursor.execute("select scope, scope_id, metric, amount from usage_reservations where reservation_id = %s", (reservation_id,))
            existing = cursor.fetchone()
            if existing is not None:
                if Reservation(*existing) != requested:
                    raise ValueError("reservation id already belongs to another usage")
                return
            cursor.execute("select coalesce(amount, 0) from usage_committed where scope = %s and scope_id = %s and metric = %s", (scope, scope_id, metric))
            committed = cursor.fetchone()[0]
            cursor.execute("select coalesce(sum(amount), 0) from usage_reservations where scope = %s and scope_id = %s and metric = %s", (scope, scope_id, metric))
            reserved = cursor.fetchone()[0]
            if committed + reserved + amount > limit_row[0]:
                raise QuotaExceeded("quota exceeded")
            cursor.execute("insert into usage_reservations values (%s, %s, %s, %s, %s)", (reservation_id, scope, scope_id, metric, amount))

    def _finish(self, reservation_id: str, *, commit: bool) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select scope, scope_id, metric, amount from usage_reservations where reservation_id = %s for update", (reservation_id,))
            row = cursor.fetchone()
            if row is None:
                return
            if commit:
                cursor.execute("""insert into usage_committed values (%s, %s, %s, %s)
                    on conflict(scope, scope_id, metric) do update set amount = usage_committed.amount + excluded.amount""", row)
            cursor.execute("delete from usage_reservations where reservation_id = %s", (reservation_id,))

    def finalize(self, reservation_id: str) -> None:
        self._finish(reservation_id, commit=True)

    def finalize_amount(self, reservation_id: str, amount: int | None = None) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select scope, scope_id, metric, amount from usage_reservations where reservation_id = %s for update", (reservation_id,))
            row = cursor.fetchone()
            if row is None:
                return
            charge = row[3] if amount is None else amount
            if charge < 0 or charge > row[3]:
                raise ValueError("charge exceeds reserved amount")
            cursor.execute("""insert into usage_committed values (%s, %s, %s, %s)
                on conflict(scope, scope_id, metric) do update set amount = usage_committed.amount + excluded.amount""", (row[0], row[1], row[2], charge))
            cursor.execute("delete from usage_reservations where reservation_id = %s", (reservation_id,))

    def release(self, reservation_id: str) -> None:
        self._finish(reservation_id, commit=False)

    def committed(self, scope: str, scope_id: str, metric: str) -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select coalesce(amount, 0) from usage_committed where scope = %s and scope_id = %s and metric = %s", (scope, scope_id, metric))
            row = cursor.fetchone()
        return row[0] if row is not None else 0
