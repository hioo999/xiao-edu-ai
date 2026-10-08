from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .dispatch_policy import AgentDispatchRequest, evaluate_dispatch


@dataclass(frozen=True)
class AgentExecutionResult:
    agent_kind: str
    html: str
    teaching_steps: list[str]


class AgentExecutor(Protocol):
    def execute(self, agent_kind: str, prompt: str) -> AgentExecutionResult: ...


class AgentDispatcher:
    def __init__(self, executor: AgentExecutor) -> None:
        self._executor = executor

    def dispatch(self, request: AgentDispatchRequest, prompt: str) -> AgentExecutionResult:
        evaluate_dispatch(request)
        return self._executor.execute(request.agent_kind, prompt)
