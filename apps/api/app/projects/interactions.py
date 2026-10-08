from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkComment:
    comment_id: str
    asset_id: str
    organization_id: str
    author_user_id: str
    author_role: str
    body: str
    created_at: str


class WorkInteractionStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._likes: set[tuple[str, str]] = set()
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute("create table if not exists work_likes (asset_id text not null, user_id text not null, primary key (asset_id, user_id))")
                connection.execute("create table if not exists work_comments (comment_id text primary key, asset_id text not null, organization_id text not null, author_user_id text not null, author_role text not null, body text not null, created_at text not null)")
            with self._connect() as connection:
                self._likes = {(row[0], row[1]) for row in connection.execute("select asset_id, user_id from work_likes")}

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("work interactions persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def toggle_like(self, asset_id: str, user_id: str, enabled: bool) -> bool:
        key = (asset_id, user_id)
        changed = False
        if enabled and key not in self._likes:
            self._likes.add(key)
            changed = True
        if not enabled and key in self._likes:
            self._likes.discard(key)
            changed = True
        if changed and self._storage_path:
            with self._connect() as connection:
                if enabled:
                    connection.execute("insert or ignore into work_likes values (?, ?)", key)
                else:
                    connection.execute("delete from work_likes where asset_id = ? and user_id = ?", key)
        return enabled

    def like_count(self, asset_id: str) -> int:
        return sum(1 for key in self._likes if key[0] == asset_id)

    def liked_by(self, asset_id: str, user_id: str) -> bool:
        return (asset_id, user_id) in self._likes

    def add_comment(self, asset_id: str, organization_id: str, author_user_id: str, author_role: str, body: str) -> WorkComment:
        comment = WorkComment(f"comment-{uuid.uuid4().hex[:12]}", asset_id, organization_id, author_user_id, author_role, body.strip(), _now())
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into work_comments values (?, ?, ?, ?, ?, ?, ?)", (comment.comment_id, comment.asset_id, comment.organization_id, comment.author_user_id, comment.author_role, comment.body, comment.created_at))
        return comment

    def list_comments(self, asset_id: str, organization_id: str) -> list[WorkComment]:
        if not self._storage_path:
            return []
        with self._connect() as connection:
            rows = connection.execute("select comment_id, asset_id, organization_id, author_user_id, author_role, body, created_at from work_comments where asset_id = ? and organization_id = ? order by created_at asc", (asset_id, organization_id)).fetchall()
        return [WorkComment(row["comment_id"], row["asset_id"], row["organization_id"], row["author_user_id"], row["author_role"], row["body"], row["created_at"]) for row in rows]
