from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import io
import json
import os
import sqlite3
import uuid
import zipfile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DeploymentRecord:
    deployment_id: str
    asset_id: str
    organization_id: str
    project_type: str
    state: str
    manifest: dict[str, object]
    env_template: dict[str, str]
    created_at: str
    updated_at: str
    published_url: str = ""


class ZipProjectAnalyzer:
    """Static, dependency-free analysis of a packaged web project."""

    def analyze(self, content: bytes) -> dict[str, object]:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            root_dirs = {name.split("/")[0] for name in names if "/" in name}
            text_names = [name for name in names if name.lower().endswith((".json", ".txt", ".py", ".js", ".ts", ".md", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".html", ".css", ".env", ".example", ".sample"))]
            lowered = {name.lower() for name in names}
            project_type = self._project_type(lowered, names)
            dependencies = self._dependencies(text_names, archive)
            env_template = self._env_template(text_names, archive, project_type)
        return {
            "fileCount": len(names),
            "topLevelDirs": sorted(root_dirs)[:20],
            "projectType": project_type,
            "entrypoints": [name for name in names if name.endswith("index.html")][:5],
            "dependencies": dependencies,
            "envTemplate": env_template,
            "hasDatabaseHint": self._has_database_hint(lowered),
        }

    def _project_type(self, lowered: set[str], names: list[str]) -> str:
        if "package.json" in lowered:
            return "node"
        if any(name.endswith("requirements.txt") or name.endswith("pyproject.toml") for name in names):
            return "python"
        if any(name.endswith("index.html") for name in names):
            return "static"
        return "unknown"

    def _dependencies(self, text_names: list[str], archive: zipfile.ZipFile) -> list[str]:
        for name in text_names:
            base = name.rsplit("/", 1)[-1].lower()
            if base == "package.json":
                try:
                    data = json.loads(archive.read(name).decode("utf-8"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    return sorted(deps)[:50]
                except Exception:
                    return []
        return []

    def _env_template(self, text_names: list[str], archive: zipfile.ZipFile, project_type: str) -> dict[str, str]:
        candidates = [name for name in text_names if name.rsplit("/", 1)[-1].lower() in {".env.example", ".env.sample", "env.example", ".env"}]
        for name in candidates:
            try:
                text = archive.read(name).decode("utf-8")
                return {key.strip(): "" for line in text.splitlines() if "=" in line and (key := line.split("=", 1)[0].strip()) and not key.startswith("#")}
            except Exception:
                continue
        defaults = {"PORT": "8080"}
        if project_type == "python":
            defaults = {"PORT": "8080", "DATABASE_URL": ""}
        return defaults

    def _has_database_hint(self, lowered: set[str]) -> bool:
        return any("sqlite" in name or "prisma" in name or "drizzle" in name or "migrations" in name for name in lowered)


class DeploymentService:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._records: dict[str, DeploymentRecord] = {}
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute("create table if not exists deployments (deployment_id text primary key, asset_id text not null, organization_id text not null, project_type text not null, state text not null, manifest text not null, env_template text not null, created_at text not null, updated_at text not null, published_url text not null default '')")
                columns = {row[1] for row in connection.execute("pragma table_info(deployments)")}
                if "published_url" not in columns:
                    connection.execute("alter table deployments add column published_url text not null default ''")
            self._load()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("deployment persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _load(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select deployment_id, asset_id, organization_id, project_type, state, manifest, env_template, created_at, updated_at, published_url from deployments").fetchall()
        self._records = {row["deployment_id"]: DeploymentRecord(row["deployment_id"], row["asset_id"], row["organization_id"], row["project_type"], row["state"], json.loads(row["manifest"]), json.loads(row["env_template"]), row["created_at"], row["updated_at"], row["published_url"]) for row in rows}

    def create(self, asset_id: str, organization_id: str, manifest: dict[str, object], env_template: dict[str, str]) -> DeploymentRecord:
        record = DeploymentRecord(f"deploy-{uuid.uuid4().hex[:12]}", asset_id, organization_id, str(manifest.get("projectType", "unknown")), "prepared", manifest, env_template, _now(), _now())
        self._records[record.deployment_id] = record
        self._persist(record)
        return record

    def _persist(self, record: DeploymentRecord) -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("""insert into deployments (
                deployment_id, asset_id, organization_id, project_type, state, manifest, env_template, created_at, updated_at, published_url
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(deployment_id) do update set state=excluded.state, updated_at=excluded.updated_at, published_url=excluded.published_url""", (
                record.deployment_id, record.asset_id, record.organization_id, record.project_type, record.state,
                json.dumps(record.manifest, ensure_ascii=False), json.dumps(record.env_template, ensure_ascii=False),
                record.created_at, record.updated_at, record.published_url,
            ))

    def get(self, deployment_id: str, organization_id: str) -> DeploymentRecord:
        record = self._records.get(deployment_id)
        if record is None or record.organization_id != organization_id:
            raise KeyError(deployment_id)
        return record

    def list_for_asset(self, asset_id: str, organization_id: str) -> list[DeploymentRecord]:
        return sorted((record for record in self._records.values() if record.asset_id == asset_id and record.organization_id == organization_id), key=lambda item: item.created_at, reverse=True)

    def publish(self, deployment_id: str, organization_id: str, published_url: str) -> DeploymentRecord:
        record = self.get(deployment_id, organization_id)
        published = DeploymentRecord(
            record.deployment_id, record.asset_id, record.organization_id, record.project_type, "published",
            record.manifest, record.env_template, record.created_at, _now(), published_url,
        )
        self._records[deployment_id] = published
        self._persist(published)
        return published


def deployment_payload(record: DeploymentRecord) -> dict[str, object]:
    return {"deploymentId": record.deployment_id, "assetId": record.asset_id, "projectType": record.project_type, "state": record.state, "manifest": record.manifest, "envTemplate": record.env_template, "createdAt": record.created_at, "updatedAt": record.updated_at, "publishedUrl": record.published_url}


class DeploymentUnavailableError(RuntimeError):
    """Raised when a real cloud deployment cannot proceed with current configuration."""


class TencentDeployer:
    """Placeholder for Tencent Cloud container deployment.

    The local platform never executes uploaded projects itself. Once real
    Tencent Cloud credentials and CVM/TKE/COS resources are provided, this
    seam is where a validated deployment record is turned into a sandboxed,
    isolated container instance with its own URL and database.
    """

    required_env = ("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY", "TENCENT_REGION")

    def validate_credentials(self, env: dict[str, str] | None = None) -> None:
        values = env if env is not None else os.environ
        missing = [key for key in self.required_env if not values.get(key)]
        if missing:
            raise DeploymentUnavailableError("tencent cloud deployment requires: " + ", ".join(missing))

    def deploy(self, record: DeploymentRecord, env_template: dict[str, str]) -> dict[str, object]:
        self.validate_credentials()
        raise DeploymentUnavailableError("live container deployment is not wired yet; connect Tencent Cloud CVM/TKE/COS and database resources first")
