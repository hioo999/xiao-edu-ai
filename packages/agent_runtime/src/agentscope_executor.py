from __future__ import annotations

from collections.abc import Callable
import asyncio
from html import escape
import inspect
from typing import Any

from .dispatcher import AgentExecutionResult


class AgentScopeExecutor:
    """Adapter seam for an AgentScope-backed factory.

    The application does not import AgentScope directly. Deployment code supplies
    a factory that creates the configured AgentScope agent for each agent kind.
    """

    def __init__(self, agent_factory: Callable[..., object], tool_executor: Any | None = None) -> None:
        self._agent_factory = agent_factory
        self._tool_executor = tool_executor

    def _build_agent(self, agent_kind: str, context: dict[str, object]) -> object:
        parameters = inspect.signature(self._agent_factory).parameters
        accepts_keyword_context = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
        keyword_context = {name: value for name, value in context.items() if accepts_keyword_context or name in parameters}
        if self._tool_executor is not None and (accepts_keyword_context or "tool_executor" in parameters):
            return self._agent_factory(agent_kind, tool_executor=self._tool_executor, **keyword_context)
        if self._tool_executor is not None and len(parameters) >= 2:
            return self._agent_factory(agent_kind, self._tool_executor)
        return self._agent_factory(agent_kind, **keyword_context)

    @staticmethod
    def _resolve(value: Any) -> Any:
        if inspect.isawaitable(value):
            return asyncio.run(value)
        return value

    def execute(self, agent_kind: str, prompt: str, **context: object) -> AgentExecutionResult:
        agent = self._build_agent(agent_kind, context)
        run = getattr(agent, "run", None)
        reply = getattr(agent, "reply", None)
        if callable(run):
            payload = self._resolve(run(prompt))
        elif callable(reply):
            payload = self._resolve(reply(prompt))
        else:
            raise LookupError("AgentScope agent does not expose run() or reply()")
        if not isinstance(payload, dict):
            content = getattr(payload, "content", payload if isinstance(payload, str) else None)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("AgentScope response must contain html or text content")
            payload = {"html": f"<main><p>{escape(content)}</p></main>", "teachingSteps": []}
        if not isinstance(payload.get("html"), str):
            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("AgentScope response must contain html")
            html = content if "<" in content else f"<main><p>{escape(content)}</p></main>"
            payload = {**payload, "html": html}
        steps = payload.get("teachingSteps", [])
        if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
            raise ValueError("AgentScope teachingSteps must be a string list")
        return AgentExecutionResult(agent_kind=agent_kind, html=payload["html"], teaching_steps=steps)
