from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import secrets
import sqlite3


@dataclass
class ShareLink:
    token: str
    project_id: str
    expires_at: datetime | None
    allow_download: bool
    revoked: bool = False
    organization_id: str = ""
    owner_user_id: str = ""


class ShareLinkService:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._links: dict[str, ShareLink] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("share persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("create table if not exists share_links (token text primary key, project_id text not null, expires_at text, allow_download integer not null, revoked integer not null, organization_id text not null, owner_user_id text not null)")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select * from share_links").fetchall()
        for row in rows:
            expires_at = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            self._links[row["token"]] = ShareLink(row["token"], row["project_id"], expires_at, bool(row["allow_download"]), bool(row["revoked"]), row["organization_id"], row["owner_user_id"])

    def _persist(self, link: ShareLink) -> None:
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into share_links values (?, ?, ?, ?, ?, ?, ?) on conflict(token) do update set revoked=excluded.revoked", (link.token, link.project_id, link.expires_at.isoformat() if link.expires_at else None, int(link.allow_download), int(link.revoked), link.organization_id, link.owner_user_id))

    def create(self, project_id: str, *, expires_at: datetime | None, allow_download: bool, organization_id: str = "", owner_user_id: str = "") -> ShareLink:
        link = ShareLink(secrets.token_urlsafe(18), project_id, expires_at, allow_download, False, organization_id, owner_user_id)
        self._links[link.token] = link
        self._persist(link)
        return link

    def revoke(self, token: str) -> None:
        link = self._links[token]
        link.revoked = True
        self._persist(link)

    def get(self, token: str) -> ShareLink:
        return self._links[token]

    def is_accessible(self, token: str) -> bool:
        link = self._links.get(token)
        return bool(link and not link.revoked and (link.expires_at is None or link.expires_at > datetime.now(timezone.utc)))


class PostgresShareLinkService(ShareLinkService):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL share link service requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_share_links (token text primary key, project_id text not null, expires_at timestamptz, allow_download boolean not null, revoked boolean not null, organization_id text not null, owner_user_id text not null)")

    def _connect_postgres(self):
        return self._psycopg.connect(self._database_url)
    @staticmethod
    def _link(row) -> ShareLink:
        return ShareLink(str(row[0]), str(row[1]), row[2], bool(row[3]), bool(row[4]), str(row[5]), str(row[6]))
    def _persist(self, link: ShareLink) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_share_links values (%s,%s,%s,%s,%s,%s,%s) on conflict(token) do update set revoked=excluded.revoked", (link.token, link.project_id, link.expires_at, link.allow_download, link.revoked, link.organization_id, link.owner_user_id))
    def get(self, token: str) -> ShareLink:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select token, project_id, expires_at, allow_download, revoked, organization_id, owner_user_id from runtime_share_links where token = %s", (token,))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(token)
        return self._link(row)
    def revoke(self, token: str) -> None:
        link = self.get(token)
        link.revoked = True
        self._persist(link)
    def is_accessible(self, token: str) -> bool:
        try:
            link = self.get(token)
        except KeyError:
            return False
        return not link.revoked and (link.expires_at is None or link.expires_at > datetime.now(timezone.utc))
