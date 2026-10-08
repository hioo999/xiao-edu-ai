from enum import StrEnum


class TaskState(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"


class ErrorCode(StrEnum):
    AUTH_EXPIRED = "AUTH_EXPIRED"
    CLASSROOM_CLOSED = "CLASSROOM_CLOSED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODERATION_BLOCKED = "MODERATION_BLOCKED"
    FILE_REJECTED = "FILE_REJECTED"
    PREVIEW_BLOCKED = "PREVIEW_BLOCKED"
