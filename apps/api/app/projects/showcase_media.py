from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets
import sqlite3


@dataclass(frozen=True)
class ShowcaseMedia:
    asset_id: str
    organization_id: str
    slot: str
    filename: str
    content_type: str
    size: int
    path: str


class ShowcaseMediaStore:
    """Private media attachments used by the authenticated showcase UI."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._database_path = self._root / "showcase-media.sqlite3"
        with self._connect() as connection:
            connection.execute("""create table if not exists showcase_media (
                asset_id text not null, organization_id text not null, slot text not null,
                filename text not null, content_type text not null, size integer not null, path text not null,
                primary key(asset_id, slot)
            )""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, asset_id: str, organization_id: str, slot: str, filename: str, content_type: str, content: bytes) -> ShowcaseMedia:
        safe_name = Path(filename).name or f"{slot}-media"
        path = self._root / f"{asset_id}-{slot}-{secrets.token_hex(5)}-{safe_name}"
        path.write_bytes(content)
        media = ShowcaseMedia(asset_id, organization_id, slot, safe_name, content_type or "application/octet-stream", len(content), str(path))
        with self._connect() as connection:
            previous = connection.execute("select path from showcase_media where asset_id = ? and slot = ?", (asset_id, slot)).fetchone()
            connection.execute("""insert into showcase_media values (?, ?, ?, ?, ?, ?, ?)
                on conflict(asset_id, slot) do update set organization_id=excluded.organization_id,
                filename=excluded.filename, content_type=excluded.content_type, size=excluded.size, path=excluded.path""", (
                media.asset_id, media.organization_id, media.slot, media.filename, media.content_type, media.size, media.path,
            ))
        if previous:
            Path(previous["path"]).unlink(missing_ok=True)
        return media

    def get(self, asset_id: str, organization_id: str, slot: str) -> ShowcaseMedia:
        with self._connect() as connection:
            row = connection.execute("select * from showcase_media where asset_id = ? and organization_id = ? and slot = ?", (asset_id, organization_id, slot)).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return ShowcaseMedia(row["asset_id"], row["organization_id"], row["slot"], row["filename"], row["content_type"], row["size"], row["path"])

    def read(self, media: ShowcaseMedia) -> bytes:
        return Path(media.path).read_bytes()
