from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets
import sqlite3


@dataclass(frozen=True)
class WorkArtifact:
    asset_id: str
    organization_id: str
    filename: str
    content_type: str
    size: int
    path: str


class WorkArtifactStore:
    """Private uploaded project files, kept separate from public work metadata."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._database_path = self._root / "work-artifacts.sqlite3"
        with self._connect() as connection:
            connection.execute("create table if not exists work_artifacts (asset_id text primary key, organization_id text not null, filename text not null, content_type text not null, size integer not null, path text not null)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, asset_id: str, organization_id: str, filename: str, content_type: str, content: bytes) -> WorkArtifact:
        safe_name = Path(filename).name or "uploaded-work"
        path = self._root / f"{asset_id}-{secrets.token_hex(5)}-{safe_name}"
        path.write_bytes(content)
        artifact = WorkArtifact(asset_id, organization_id, safe_name, content_type or "application/octet-stream", len(content), str(path))
        with self._connect() as connection:
            connection.execute("insert into work_artifacts values (?, ?, ?, ?, ?, ?) on conflict(asset_id) do update set filename=excluded.filename, content_type=excluded.content_type, size=excluded.size, path=excluded.path", (artifact.asset_id, artifact.organization_id, artifact.filename, artifact.content_type, artifact.size, artifact.path))
        return artifact

    def get(self, asset_id: str, organization_id: str) -> WorkArtifact:
        with self._connect() as connection:
            row = connection.execute("select * from work_artifacts where asset_id = ? and organization_id = ?", (asset_id, organization_id)).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return WorkArtifact(row["asset_id"], row["organization_id"], row["filename"], row["content_type"], row["size"], row["path"])

    def read(self, artifact: WorkArtifact) -> bytes:
        return Path(artifact.path).read_bytes()

    def delete(self, asset_id: str, organization_id: str) -> None:
        artifact = self.get(asset_id, organization_id)
        Path(artifact.path).unlink(missing_ok=True)
        with self._connect() as connection:
            connection.execute("delete from work_artifacts where asset_id = ? and organization_id = ?", (asset_id, organization_id))
