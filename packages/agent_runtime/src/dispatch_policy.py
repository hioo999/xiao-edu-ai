from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AgentDispatchRequest:
    agent_kind: str
    capability: str
    classroom_open: bool
    feature_enabled: bool
    quota_available: bool
    model_available: bool
    allow_foreign: bool
    model_region: Literal["domestic", "foreign"]
    mcp_approved: bool


@dataclass(frozen=True)
class DispatchDecision:
    allowed: bool
    agent_kind: str


class DispatchDenied(PermissionError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def evaluate_dispatch(request: AgentDispatchRequest) -> DispatchDecision:
    checks = (
        (request.classroom_open, "CLASSROOM_CLOSED", "classroom is closed"),
        (request.feature_enabled, "FEATURE_DISABLED", "feature is disabled"),
        (request.quota_available, "QUOTA_EXCEEDED", "quota is exhausted"),
        (request.model_available, "MODEL_UNAVAILABLE", "model is unavailable"),
        (request.mcp_approved, "MCP_NOT_APPROVED", "MCP is not approved"),
        (
            request.model_region != "foreign" or request.allow_foreign,
            "FOREIGN_MODEL_DENIED",
            "foreign model is not allowed",
        ),
    )
    for passed, code, message in checks:
        if not passed:
            raise DispatchDenied(code, message)
    return DispatchDecision(allowed=True, agent_kind=request.agent_kind)
