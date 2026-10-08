from __future__ import annotations

from dataclasses import dataclass
import os
import sqlite3


@dataclass(frozen=True)
class DeploymentStorage:
    mode: str
    database_url: str | None
    redis_url: str | None


def deployment_storage_from_env() -> DeploymentStorage:
    mode = os.getenv("PLATFORM_STORAGE_MODE", "sqlite").strip().lower()
    database_url = os.getenv("DATABASE_URL", "").strip() or None
    redis_url = os.getenv("REDIS_URL", "").strip() or None
    if mode not in {"sqlite", "postgres"}:
        raise RuntimeError("PLATFORM_STORAGE_MODE must be sqlite or postgres")
    if mode == "postgres" and not database_url:
        raise RuntimeError("DATABASE_URL is required when PLATFORM_STORAGE_MODE=postgres")
    if mode == "postgres" and not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("DATABASE_URL must use a PostgreSQL URL")
    if redis_url and not redis_url.startswith(("redis://", "rediss://")):
        raise RuntimeError("REDIS_URL must use redis:// or rediss://")
    return DeploymentStorage(mode, database_url, redis_url)


def storage_is_ready(storage: DeploymentStorage, sqlite_path: str) -> bool:
    """Check the configured primary database without exposing connection details."""
    try:
        if storage.mode == "sqlite":
            with sqlite3.connect(sqlite_path) as connection:
                connection.execute("select 1")
            return True
        import psycopg
        with psycopg.connect(storage.database_url) as connection, connection.cursor() as cursor:
            cursor.execute("select 1")
            return cursor.fetchone() == (1,)
    except Exception:
        return False
