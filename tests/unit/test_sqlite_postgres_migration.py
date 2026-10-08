import sqlite3

import pytest

from scripts.migrate_sqlite_to_postgres import copy_rows, existing_columns


pytestmark = pytest.mark.unit


def test_migration_reads_available_sqlite_columns(tmp_path) -> None:
    path = tmp_path / "platform.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table sample (id text primary key, value text)")
    with sqlite3.connect(path) as connection:
        assert existing_columns(connection, "sample") == {"id", "value"}


def test_migration_skips_a_table_with_missing_columns(tmp_path) -> None:
    class FakePostgres:
        def cursor(self):
            raise AssertionError("a skipped table must not open a PostgreSQL cursor")
    path = tmp_path / "platform.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table sample (id text primary key)")
        assert copy_rows(connection, FakePostgres(), "sample", "target", ("id", "missing")) == 0
