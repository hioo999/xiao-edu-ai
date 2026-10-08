import pytest

from apps.api.app.media.jobs import JobState, MediaJob, MediaJobLedger


def test_media_job_moves_from_queued_to_success() -> None:
    ledger = MediaJobLedger()
    job = ledger.create("video", "student-001")

    ledger.start(job.job_id)
    ledger.succeed(job.job_id, asset_id="asset-001")

    assert ledger.get(job.job_id).state is JobState.SUCCEEDED
    assert ledger.get(job.job_id).asset_id == "asset-001"


def test_failed_job_can_retry_but_cannot_succeed_before_running() -> None:
    ledger = MediaJobLedger()
    job = ledger.create("image", "student-001")

    with pytest.raises(ValueError):
        ledger.succeed(job.job_id, asset_id="asset-001")
    ledger.start(job.job_id)
    ledger.fail(job.job_id, "provider timeout")
    ledger.retry(job.job_id)

    assert ledger.get(job.job_id).state is JobState.QUEUED


def test_sqlite_ledger_refreshes_state_across_process_instances(tmp_path) -> None:
    storage_path = tmp_path / "media-jobs.sqlite"
    api_ledger = MediaJobLedger(storage_path)
    worker_ledger = MediaJobLedger(storage_path)

    job = api_ledger.create("image", "student-001", prompt="a red fox")
    worker_ledger.start(job.job_id)
    worker_ledger.update_progress(job.job_id, 42)
    worker_ledger.succeed(job.job_id, asset_id="asset-001")

    refreshed = api_ledger.get(job.job_id)
    assert refreshed.state is JobState.SUCCEEDED
    assert refreshed.asset_id == "asset-001"
    assert refreshed.progress == 100
    assert refreshed.started_at is not None
    assert refreshed.last_heartbeat_at is not None


def test_sqlite_ledger_tracks_dead_letters_and_worker_heartbeat(tmp_path) -> None:
    ledger = MediaJobLedger(tmp_path / "media-jobs.sqlite")
    job = ledger.create("video", "student-001")
    ledger.start(job.job_id)
    ledger.fail(job.job_id, "provider unavailable")

    ledger.mark_dead_letter(job.job_id, "provider unavailable")
    assert ledger.list_dead_letters() == [{"jobId": job.job_id, "error": "provider unavailable"}]

    ledger.heartbeat()
    status = ledger.worker_status()
    assert status["workerReady"] is True
    assert status["deadLetterDepth"] == 1
    assert status["queueDepth"] == 0

    assert ledger.retry_dead_letter(job.job_id) is True
    assert ledger.list_dead_letters() == []
    assert ledger.get(job.job_id).state is JobState.QUEUED


def test_sqlite_ledger_clear_dead_letters(tmp_path) -> None:
    ledger = MediaJobLedger(tmp_path / "media-jobs.sqlite")
    first = ledger.create("image", "student-001")
    second = ledger.create("image", "student-001")
    ledger.mark_dead_letter(first.job_id, "bad provider")
    ledger.mark_dead_letter(second.job_id, "timeout")

    assert ledger.clear_dead_letters() == 2
    assert ledger.list_dead_letters() == []
