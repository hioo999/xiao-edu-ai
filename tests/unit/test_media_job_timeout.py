from datetime import datetime, timedelta, timezone

from apps.api.app.media.jobs import JobState, MediaJobLedger


def test_start_and_progress_record_worker_heartbeat() -> None:
    ledger = MediaJobLedger()
    job = ledger.create("video", "student-1")

    ledger.start(job.job_id)
    started = ledger.get(job.job_id).last_heartbeat_at
    assert ledger.get(job.job_id).started_at is not None
    assert started is not None

    ledger.update_progress(job.job_id, 20)
    assert ledger.get(job.job_id).last_heartbeat_at >= started


def test_recover_stale_running_marks_job_failed() -> None:
    ledger = MediaJobLedger()
    job = ledger.create("image", "student-1")
    ledger.start(job.job_id)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    ledger.get(job.job_id).started_at = stale
    ledger.get(job.job_id).last_heartbeat_at = stale

    assert ledger.recover_stale_running(60) == [job.job_id]
    assert ledger.get(job.job_id).state is JobState.FAILED
    assert ledger.get(job.job_id).error == "worker heartbeat timeout"


def test_recent_running_job_is_not_recovered() -> None:
    ledger = MediaJobLedger()
    job = ledger.create("image", "student-1")
    ledger.start(job.job_id)

    assert ledger.recover_stale_running(60) == []
    assert ledger.get(job.job_id).state is JobState.RUNNING
