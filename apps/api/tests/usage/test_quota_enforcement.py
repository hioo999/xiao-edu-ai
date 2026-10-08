import pytest

from apps.api.app.usage.service import QuotaExceeded, UsageLedger


def test_reservation_prevents_exceeding_student_quota() -> None:
    ledger = UsageLedger({("student", "student-001", "text"): 3})

    ledger.reserve("student", "student-001", "text", 2, reservation_id="task-001")

    with pytest.raises(QuotaExceeded):
        ledger.reserve("student", "student-001", "text", 2, reservation_id="task-002")


def test_retrying_same_reservation_does_not_double_charge() -> None:
    ledger = UsageLedger({("student", "student-001", "image"): 2})

    ledger.reserve("student", "student-001", "image", 1, reservation_id="task-001")
    ledger.reserve("student", "student-001", "image", 1, reservation_id="task-001")
    ledger.finalize("task-001")

    assert ledger.committed("student", "student-001", "image") == 1


def test_failed_task_releases_reserved_quota() -> None:
    ledger = UsageLedger({("student", "student-001", "video_seconds"): 60})

    ledger.reserve("student", "student-001", "video_seconds", 45, reservation_id="task-001")
    ledger.release("task-001")

    ledger.reserve("student", "student-001", "video_seconds", 60, reservation_id="task-002")
    assert ledger.committed("student", "student-001", "video_seconds") == 0


def test_quota_scope_falls_back_from_student_to_class_to_organization() -> None:
    ledger = UsageLedger({
        ("organization", "org-001", "text"): 10,
        ("class", "class-001", "text"): 2,
    })

    selected = ledger.reserve_with_fallback(
        [("student", "student-001"), ("class", "class-001"), ("organization", "org-001")],
        "text",
        1,
        reservation_id="task-001",
    )

    assert selected == ("class", "class-001")
    ledger.finalize("task-001")
    assert ledger.committed("class", "class-001", "text") == 1


def test_reservation_survives_api_worker_process_restart(tmp_path) -> None:
    database_path = tmp_path / "platform.db"
    first = UsageLedger({}, database_path)
    first.set_limit("organization", "org-001", "image", 2)
    first.reserve("organization", "org-001", "image", 1, reservation_id="job-001")

    restarted = UsageLedger({}, database_path)
    restarted.finalize("job-001")

    assert restarted.committed("organization", "org-001", "image") == 1
    assert restarted.summary("organization", "org-001")[0]["reserved"] == 0
