"""Copy the platform's SQLite data into PostgreSQL runtime tables.

Run only after setting PLATFORM_STORAGE_MODE=postgres and DATABASE_URL. The
script is idempotent: target rows are replaced by their source primary key.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
from typing import Iterable


TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("platform_users", "platform_users", ("username", "user_id", "organization_id", "role", "password_hash", "enabled", "expires_at", "class_id")),
    ("access_sessions", "access_sessions", ("token_hash", "user_id", "organization_id", "role", "expires_at")),
    ("model_providers", "runtime_model_providers", ("provider_id", "organization_id", "capability", "region", "priority", "encrypted_api_key", "provider_kind", "model_id", "base_url", "enabled", "model_catalog")),
    ("model_calls", "model_calls", ("organization_id", "provider_id", "capability", "outcome", "created_at")),
    ("media_jobs", "media_jobs", ("job_id", "kind", "owner_user_id", "organization_id", "prompt", "project_id", "reference_image_url", "provider_id", "state", "error", "asset_id", "external_task_id", "attempts", "progress")),
    ("usage_limits", "usage_limits", ("scope", "scope_id", "metric", "amount")),
    ("usage_committed", "usage_committed", ("scope", "scope_id", "metric", "amount")),
    ("usage_reservations", "usage_reservations", ("reservation_id", "scope", "scope_id", "metric", "amount")),
    ("creative_assets", "runtime_creative_assets", ("asset_id", "project_id", "organization_id", "owner_user_id", "kind", "title", "preview_url", "prompt", "review_state", "featured")),
    ("courses", "runtime_courses", ("course_id", "organization_id", "author_user_id", "title", "summary", "blocks", "teacher_script", "prompt_examples", "student_flow", "published")),
    ("course_classrooms", "runtime_course_classrooms", ("course_id", "class_id", "organization_id")),
    ("knowledge_documents", "runtime_knowledge_documents", ("document_id", "scope", "scope_id", "title", "organization_id", "content")),
    ("managed_tools", "runtime_managed_tools", ("tool_id", "kind", "name", "capabilities", "enabled", "organization_id")),
    ("managed_agents", "runtime_managed_agents", ("agent_id", "name", "capability", "grade_range", "published", "organization_id")),
    ("classrooms", "runtime_classrooms", ("class_id", "organization_id", "state", "teachers", "schedule")),
    ("html_projects", "runtime_html_projects", ("project_id", "owner_user_id", "current_version_id")),
    ("html_versions", "runtime_html_versions", ("version_id", "project_id", "title", "html", "teaching_steps", "position")),
    ("share_links", "runtime_share_links", ("token", "project_id", "expires_at", "allow_download", "revoked", "organization_id", "owner_user_id")),
    ("audit_records", "runtime_audit_records", ("organization_id", "actor_id", "action", "target_type", "target_id", "created_at")),
    ("organization_settings", "runtime_organization_settings", ("organization_id", "display_name", "student_home_enabled", "maintenance_message", "showcase_columns", "showcase_rows", "showcase_sort", "showcase_kind")),
    ("inspiration_cases", "runtime_inspiration_cases", ("case_id", "title", "grade_min", "grade_max", "interests", "difficulty", "duration_minutes", "prompt", "capability", "organization_ids")),
    ("inspiration_favorites", "runtime_inspiration_favorites", ("case_id", "user_id", "organization_id")),
    ("learning_events", "runtime_learning_events", ("student_id", "event_type", "label")),
)


def existing_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(f"pragma table_info({table_name})")}


def copy_rows(sqlite_connection: sqlite3.Connection, postgres_connection, source_table: str, target_table: str, columns: tuple[str, ...]) -> int:
    if not set(columns).issubset(existing_columns(sqlite_connection, source_table)):
        return 0
    quoted_columns = ", ".join(columns)
    placeholders = ", ".join("%s" for _ in columns)
    rows = sqlite_connection.execute(f"select {quoted_columns} from {source_table}").fetchall()
    if not rows:
        return 0
    with postgres_connection.cursor() as cursor:
        cursor.executemany(f"insert into {target_table} ({quoted_columns}) values ({placeholders}) on conflict do nothing", rows)
    return len(rows)


def migrate(sqlite_path: Path, database_url: str) -> dict[str, int]:
    if not sqlite_path.exists():
        raise FileNotFoundError(sqlite_path)
    os.environ["PLATFORM_STORAGE_MODE"] = "postgres"
    os.environ["DATABASE_URL"] = database_url
    from apps.api.app.main import create_app
    create_app()  # Initialize every PostgreSQL runtime table before copying.
    import psycopg
    copied: dict[str, int] = {}
    with sqlite3.connect(sqlite_path) as sqlite_connection, psycopg.connect(database_url) as postgres_connection:
        for source_table, target_table, columns in TABLES:
            copied[source_table] = copy_rows(sqlite_connection, postgres_connection, source_table, target_table, columns)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate platform SQLite data into PostgreSQL")
    parser.add_argument("--sqlite-path", default=os.getenv("PLATFORM_DB_PATH", "var/platform.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    arguments = parser.parse_args()
    if not arguments.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")
    copied = migrate(Path(arguments.sqlite_path), arguments.database_url)
    for table_name, count in copied.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
