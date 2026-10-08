import json
import logging

import pytest

from apps.api.app.core.observability import JsonLogFormatter


pytestmark = pytest.mark.unit


def test_json_log_formatter_keeps_only_safe_structured_fields() -> None:
    record = logging.LogRecord("platform", logging.INFO, "", 0, "processed", (), None)
    record.event = "media.completed"
    record.job_id = "job-1"
    record.api_key = "must-not-appear"

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["event"] == "media.completed"
    assert payload["job_id"] == "job-1"
    assert "api_key" not in payload
