from apps.api.app.core.errors import ErrorCode, TaskState


def test_task_states_and_error_codes_are_stable() -> None:
    assert TaskState.QUEUED.value == "queued"
    assert TaskState.SUCCEEDED.value == "succeeded"
    assert ErrorCode.CLASSROOM_CLOSED.value == "CLASSROOM_CLOSED"
    assert ErrorCode.MODERATION_BLOCKED.value == "MODERATION_BLOCKED"
