from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone


class JsonLogFormatter(logging.Formatter):
    """CLS-friendly stdout JSON without request bodies or credentials."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("event", "method", "path", "status_code", "duration_ms", "organization_id", "job_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_structured_logging() -> None:
    if os.getenv("STRUCTURED_LOGGING", "true").lower() not in {"1", "true", "yes"}:
        return
    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonLogFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
