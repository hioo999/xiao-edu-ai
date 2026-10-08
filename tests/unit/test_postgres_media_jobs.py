import sys
import types

import pytest

from apps.api.app.media.jobs import JobState, PostgresMediaJobLedger


pytestmark = pytest.mark.unit


class _FakePostgresState:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[object, ...]] = {}


class _FakeCursor:
    def __init__(self, state: _FakePostgresState) -> None:
        self.state = state
        self._rows: list[tuple[object, ...]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, values: tuple[object, ...] | None = None) -> None:
        normalized = " ".join(query.lower().split())
        if normalized.startswith("insert into media_jobs"):
            assert values is not None
            self.state.rows[str(values[0])] = values
            self._rows = []
        elif normalized.startswith("update media_jobs set state"):
            assert values is not None
            row = self.state.rows.get(str(values[1]))
            if row is None or row[8] != values[2]:
                self._rows = []
            else:
                updated = list(row)
                updated[8] = values[0]
                updated[12] = int(row[12]) + 1
                updated[13] = max(int(row[13]), 5)
                self.state.rows[str(values[1])] = updated
                self._rows = [(values[1],)]
        elif "where job_id = %s" in normalized:
            assert values is not None
            row = self.state.rows.get(str(values[0]))
            self._rows = [row] if row else []
        elif normalized.startswith("select * from media_jobs where"):
            rows = list(self.state.rows.values())
            if "owner_user_id = %s" in normalized:
                assert values is not None
                rows = [row for row in rows if row[2] == values[0] and row[3] == values[1]]
            elif "organization_id = %s" in normalized:
                assert values is not None
                rows = [row for row in rows if row[3] == values[0]]
            elif "state in (%s, %s)" in normalized:
                assert values is not None
                rows = [row for row in rows if row[8] in values]
            self._rows = sorted(rows, key=lambda row: str(row[0]), reverse=True)
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, state: _FakePostgresState) -> None:
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.state)


def test_postgres_media_jobs_share_state_across_ledger_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _FakePostgresState()
    module = types.SimpleNamespace(connect=lambda _url: _FakeConnection(state))
    monkeypatch.setitem(sys.modules, "psycopg", module)

    producer = PostgresMediaJobLedger("postgresql://example")
    job = producer.create("image", "student-1", organization_id="school-1", prompt="画一只猫")
    producer.start(job.job_id)
    producer.update_progress(job.job_id, 68)

    worker = PostgresMediaJobLedger("postgresql://example")
    pending = worker.list_pending()
    assert [(item.job_id, item.state, item.progress) for item in pending] == [(job.job_id, JobState.RUNNING, 68)]

    worker.succeed(job.job_id, asset_id="asset-1")
    completed = producer.get(job.job_id)
    assert completed.state is JobState.SUCCEEDED
    assert completed.asset_id == "asset-1"
    assert completed.progress == 100


def test_postgres_media_job_can_only_be_claimed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _FakePostgresState()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda _url: _FakeConnection(state)))
    ledger = PostgresMediaJobLedger("postgresql://example")
    job = ledger.create("video", "student-1", organization_id="school-1")

    ledger.start(job.job_id)
    with pytest.raises(ValueError, match="only queued jobs"):
        ledger.start(job.job_id)
