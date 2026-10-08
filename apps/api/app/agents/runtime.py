from __future__ import annotations

from html import escape
from importlib import import_module
import json
import os
from collections.abc import Callable
from typing import Protocol

from apps.api.app.models.gateway import ModelGateway
from packages.agent_runtime.src.agentscope_executor import AgentScopeExecutor
from packages.agent_runtime.src.dispatcher import AgentExecutionResult
from packages.agent_runtime.src.mcp_client import build_mcp_clients_from_env
from packages.agent_runtime.src.tool_policy import McpServer, McpToolExecutor, ToolPolicy


class AgentRuntime(Protocol):
    def execute(self, *, agent_id: str, capability: str, organization_id: str, prompt: str) -> AgentExecutionResult: ...


class GatewayAgentRuntime:
    """Default runtime for deployed agents before an AgentScope service is configured."""

    def __init__(self, gateway: ModelGateway, skill_loader: Callable[[str, str], list[str]] | None = None) -> None:
        self._gateway = gateway
        self._skill_loader = skill_loader

    def execute(self, *, agent_id: str, capability: str, organization_id: str, prompt: str) -> AgentExecutionResult:
        skill_instructions = self._skill_loader(organization_id, capability) if self._skill_loader else []
        instruction = self._instruction(capability, prompt, skill_instructions)
        generated = self._gateway.generate_text(organization_id, instruction)
        content = generated.content
        html = content if capability == "html" and "<" in content else f"<main><p>{escape(content)}</p></main>"
        return AgentExecutionResult(agent_kind=agent_id, html=html, teaching_steps=self._steps(capability, prompt))

    @staticmethod
    def _instruction(capability: str, prompt: str, skill_instructions: list[str] | None = None) -> str:
        skills = "\n".join(f"- {instruction}" for instruction in skill_instructions or [])
        skill_context = f"\n\n请同时遵守以下已启用的教学规则：\n{skills}" if skills else ""
        if capability == "html":
            return f"为小学 3-6 年级学生制作安全的单文件 HTML 网页。只返回 HTML，不要脚本或外部资源。需求：{prompt}{skill_context}"
        return f"你是小学 AI 创作课的 {capability} 智能体。用积极、具体、适合儿童的中文帮助学生完成：{prompt}{skill_context}"

    @staticmethod
    def _steps(capability: str, prompt: str) -> list[str]:
        return [f"先理解“{prompt[:24]}”想表达的主题。", f"用 {capability} 创作把主题变成作品。", "预览结果，再告诉智能体想怎样改进。"]


class AgentScopeRuntime:
    """Adapter for a deployment-supplied AgentScope factory.

    The factory stays in deployment configuration so vendor model keys and tools
    never become part of application routes.
    """

    def __init__(
        self,
        agent_factory,
        mcp_server_loader: Callable[[str], list[McpServer]] | None = None,
        skill_loader: Callable[[str, str], list[str]] | None = None,
    ) -> None:
        try:
            import agentscope  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("agentscope is not installed; install the production agent runtime dependency") from exc
        self._agent_factory = agent_factory
        self._mcp_server_loader = mcp_server_loader
        self._skill_loader = skill_loader
        self._mcp_clients = build_mcp_clients_from_env()

    def execute(self, *, agent_id: str, capability: str, organization_id: str, prompt: str) -> AgentExecutionResult:
        approved_servers = self._mcp_server_loader(organization_id) if self._mcp_server_loader else []
        connected_servers = [server for server in approved_servers if server.server_id in self._mcp_clients]
        tool_executor = McpToolExecutor(policy=ToolPolicy(servers=connected_servers), clients=self._mcp_clients) if connected_servers else None
        return AgentScopeExecutor(self._agent_factory, tool_executor).execute(
            agent_id,
            prompt,
            organization_id=organization_id,
            capability=capability,
            skill_instructions=self._skill_loader(organization_id, capability) if self._skill_loader else [],
        )


def build_agent_runtime(
    gateway: ModelGateway,
    mcp_server_loader: Callable[[str], list[McpServer]] | None = None,
    skill_loader: Callable[[str, str], list[str]] | None = None,
) -> AgentRuntime:
    """Select the configured AgentScope factory, with the gateway runtime as a safe default.

    Set ``AGENTSCOPE_AGENT_FACTORY`` to ``package.module:factory`` in production.
    The factory receives an agent id and must return the application's AgentScope
    bridge object exposing ``run(prompt)``.
    """

    factory_path = os.getenv("AGENTSCOPE_AGENT_FACTORY", "").strip()
    if not factory_path:
        return GatewayAgentRuntime(gateway, skill_loader)
    module_name, separator, attribute_name = factory_path.partition(":")
    if not separator or not module_name or not attribute_name:
        raise RuntimeError("AGENTSCOPE_AGENT_FACTORY must use package.module:factory format")
    module = import_module(module_name)
    agent_factory = getattr(module, attribute_name, None)
    if not callable(agent_factory):
        raise RuntimeError("AGENTSCOPE_AGENT_FACTORY must reference a callable factory")
    return AgentScopeRuntime(agent_factory, mcp_server_loader, skill_loader)


def agentscope_readiness() -> dict[str, object]:
    """Expose deployment-safe AgentScope/MCP readiness without credentials."""
    factory_path = os.getenv("AGENTSCOPE_AGENT_FACTORY", "").strip()
    mcp_servers = os.getenv("AGENTSCOPE_MCP_SERVERS", "").strip()
    if not factory_path:
        return {
            "mode": "gateway",
            "ready": True,
            "reason": "AgentScope factory is not configured",
            "mcpServers": [],
            "checks": [{"id": "factory", "ready": False, "detail": "未配置 AgentScope；当前使用 Gateway 运行模式。"}],
        }
    module_name, separator, attribute_name = factory_path.partition(":")
    if not separator or not module_name or not attribute_name:
        return {
            "mode": "agentscope",
            "ready": False,
            "reason": "AGENTSCOPE_AGENT_FACTORY must use package.module:factory format",
            "mcpServers": [],
            "checks": [{"id": "factory", "ready": False, "detail": "工厂路径格式错误。"}],
        }
    try:
        configured_servers = json.loads(mcp_servers or "[]")
    except json.JSONDecodeError:
        return {"mode": "agentscope", "ready": False, "reason": "AGENTSCOPE_MCP_SERVERS must be a JSON string list", "mcpServers": [], "checks": []}
    if not isinstance(configured_servers, list) or not all(isinstance(server, str) and server.strip() for server in configured_servers):
        return {"mode": "agentscope", "ready": False, "reason": "AGENTSCOPE_MCP_SERVERS must contain server names only", "mcpServers": [], "checks": []}
    api_key_ready = bool(os.getenv("AGENTSCOPE_API_KEY", "").strip())
    model_ready = bool(os.getenv("AGENTSCOPE_MODEL_ID", "").strip())
    sdk_ready = False
    factory_ready = False
    try:
        import agentscope  # noqa: F401
        sdk_ready = True
        module = import_module(module_name)
        factory_ready = callable(getattr(module, attribute_name, None))
    except (ImportError, ModuleNotFoundError, AttributeError):
        pass
    try:
        connections = json.loads(os.getenv("MCP_SERVER_CONNECTIONS", "[]") or "[]")
    except json.JSONDecodeError:
        connections = []
    connection_ids = {item.get("id") for item in connections if isinstance(item, dict) and isinstance(item.get("id"), str)}
    mcp_ready = all(server in connection_ids for server in configured_servers)
    checks = [
        {"id": "factory", "ready": factory_ready, "detail": "智能体工厂可导入。" if factory_ready else "无法导入已配置的智能体工厂。"},
        {"id": "sdk", "ready": sdk_ready, "detail": "AgentScope 运行时已安装。" if sdk_ready else "尚未安装 AgentScope 运行时。"},
        {"id": "apiKey", "ready": api_key_ready, "detail": "已配置 AgentScope 模型密钥。" if api_key_ready else "尚未配置 AgentScope 模型密钥。"},
        {"id": "model", "ready": model_ready, "detail": "已配置 AgentScope 模型名称。" if model_ready else "尚未配置 AgentScope 模型名称。"},
        {"id": "mcp", "ready": mcp_ready, "detail": "MCP 连接配置完整。" if mcp_ready else "有已启用的 MCP 名称未匹配部署连接。"},
    ]
    ready = factory_ready and sdk_ready and api_key_ready and model_ready and mcp_ready
    if not factory_ready or not sdk_ready:
        reason = "install AgentScope and provide an importable factory"
    elif not api_key_ready or not model_ready:
        reason = "AgentScope API Key or model ID is not configured"
    elif not mcp_ready:
        reason = "configured MCP servers are missing deployment connections"
    else:
        reason = "ready"
    return {"mode": "agentscope", "ready": ready, "reason": reason, "mcpServers": configured_servers, "checks": checks}
