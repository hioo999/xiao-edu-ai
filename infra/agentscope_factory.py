"""Production AgentScope factory for the platform's optional agent runtime.

Set ``AGENTSCOPE_AGENT_FACTORY=infra.agentscope_factory:create_agent`` and
provide deployment-only ``AGENTSCOPE_API_KEY`` and ``AGENTSCOPE_MODEL_ID``.
This module never receives or exposes credentials through browser requests.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from collections.abc import Callable
from typing import Any


AGENT_PROMPTS = {
    "writing-coach": "你是适合小学 3-6 年级学生的写作小老师。用积极、具体、循序渐进的中文帮助学生创作。",
    "painting-coach": "你是适合小学 3-6 年级学生的绘画灵感师。把学生想法整理为安全、清晰、可用于图像生成的中文提示词。",
    "web-coach": "你是适合小学 4-6 年级学生的网页创作伙伴。只返回安全的单文件 HTML，不使用外部资源或危险脚本。",
    "video-coach": "你是适合小学 4-6 年级学生的视频故事导演。把学生想法整理为安全、分镜清晰的视频生成提示词。",
}


def system_prompt_for(agent_id: str, capability: str, skill_instructions: list[str] | None = None) -> str:
    prompt = AGENT_PROMPTS.get(agent_id, f"你是小学 AI 创作课的 {capability} 智能体。请用安全、鼓励性的中文协助学生。")
    skills = [instruction.strip() for instruction in skill_instructions or [] if instruction.strip()]
    if skills:
        prompt += "\n\n请同时遵守以下已启用的教学规则：\n" + "\n".join(f"- {instruction}" for instruction in skills)
    return prompt


def _resolve(value: Any) -> Any:
    return asyncio.run(value) if inspect.isawaitable(value) else value


def _content_from_response(response: Any) -> str:
    """Extract text from AgentScope message/content shapes without SDK coupling."""
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        return _content_from_response(response.get("content", ""))
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        return _content_from_response(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text", item.get("content", ""))
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(item, "text", getattr(item, "content", ""))
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part.strip())
    return ""


class AgentScopeBridge:
    """Adapt AgentScope's async reply interface to the platform runtime contract."""

    def __init__(self, agent_id: str, capability: str, agent: object, message_factory: Callable[..., object]) -> None:
        self._agent_id = agent_id
        self._capability = capability
        self._agent = agent
        self._message_factory = message_factory

    def run(self, prompt: str) -> dict[str, object]:
        reply = getattr(self._agent, "reply", None)
        if not callable(reply):
            raise RuntimeError("configured AgentScope agent does not expose reply()")
        response = _resolve(reply(self._message_factory("student", prompt, role="user")))
        content = _content_from_response(response)
        if not content:
            raise ValueError("AgentScope agent returned an empty response")
        return {
            "content": content,
            "teachingSteps": [
                "先读一读自己的创作目标。",
                f"根据 {self._capability} 小老师的建议完成第一版。",
                "检查作品后，再说出想改进的地方。",
            ],
        }


def _approved_mcp_tool(tool_executor: object | None) -> Callable[[str, str, str], str] | None:
    if tool_executor is None:
        return None

    def call_approved_mcp(server_id: str, capability: str, arguments_json: str = "{}") -> str:
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            raise ValueError("arguments_json must be a JSON object") from exc
        if not isinstance(arguments, dict):
            raise ValueError("arguments_json must be a JSON object")
        result = tool_executor.execute(server_id, capability, arguments)
        return json.dumps(result, ensure_ascii=False, default=str)

    return call_approved_mcp


def create_agent(
    agent_id: str,
    tool_executor: object | None = None,
    *,
    organization_id: str | None = None,
    capability: str = "text",
    skill_instructions: list[str] | None = None,
) -> AgentScopeBridge:
    """Create an AgentScope ReAct agent using an OpenAI-compatible endpoint."""
    try:
        from agentscope.agent import Agent
        from agentscope.credential import OpenAICredential
        from agentscope.formatter import OpenAIChatFormatter
        from agentscope.message import UserMsg
        from agentscope.model import OpenAIChatModel
        from agentscope.permission import PermissionBehavior, PermissionDecision
        from agentscope.tool import FunctionTool, Toolkit
    except ImportError as exc:
        raise RuntimeError("AgentScope runtime is not installed; install apps/api[agentscope] before enabling this factory") from exc

    api_key = os.getenv("AGENTSCOPE_API_KEY", "").strip()
    model_id = os.getenv("AGENTSCOPE_MODEL_ID", "").strip()
    base_url = os.getenv("AGENTSCOPE_BASE_URL", "").strip()
    if not api_key or not model_id:
        raise RuntimeError("AGENTSCOPE_API_KEY and AGENTSCOPE_MODEL_ID are required for the AgentScope factory")

    credential_options: dict[str, object] = {"api_key": api_key}
    if base_url:
        credential_options["base_url"] = base_url.rstrip("/")
    approved_mcp_tool = _approved_mcp_tool(tool_executor)
    tools = []
    if approved_mcp_tool is not None:
        tools.append(FunctionTool(
            approved_mcp_tool,
            permission=PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="平台已批准此 MCP 调用。",
            ),
        ))
    toolkit = Toolkit(tools=tools)
    system_prompt = system_prompt_for(agent_id, capability, skill_instructions)
    if approved_mcp_tool is not None:
        system_prompt += " 如需调用外部工具，只能调用 call_approved_mcp，并且只能使用已获平台批准的服务器和能力。"
    agent = Agent(
        name=agent_id,
        system_prompt=system_prompt,
        model=OpenAIChatModel(
            credential=OpenAICredential(**credential_options),
            model=model_id,
            stream=False,
            formatter=OpenAIChatFormatter(),
        ),
        toolkit=toolkit,
    )
    return AgentScopeBridge(agent_id, capability, agent, UserMsg)
