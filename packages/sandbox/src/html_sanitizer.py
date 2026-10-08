from __future__ import annotations

import re


SCRIPT_TAG = re.compile(r"<script[\s\S]*?</script\s*>", re.IGNORECASE)
EVENT_HANDLER = re.compile(r"\s+on[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
JAVASCRIPT_URL = re.compile(r"(href|src)\s*=\s*(['\"])javascript:[^'\"]*\2", re.IGNORECASE)


def sanitize_html(html: str) -> str:
    sanitized = SCRIPT_TAG.sub("", html)
    sanitized = EVENT_HANDLER.sub("", sanitized)
    return JAVASCRIPT_URL.sub(r"\1=\2#\2", sanitized)
