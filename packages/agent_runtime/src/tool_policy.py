from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from .mcp_client import McpClient


@dataclass(frozen=True)
class McpServer:
    server_id: str
    approved: bool
    capabilities: set[str]


class ToolPolicy:
    def __init__(self, *, servers: list[McpServer]) -> None:
        self._servers = {server.server_id: server for server in servers}

    def can_use(self, server_id: str, capability: str) -> bool:
        server = self._servers.get(server_id)
        return bool(server and server.approved and capability in server.capabilities)

    def require(self, server_id: str, capability: str) -> None:
        if not self.can_use(server_id, capability):
            raise PermissionError("MCP capability is not approved")


class ToolExecutor:
    """Execute only explicitly registered and policy-approved tools."""

    def __init__(self, *, policy: ToolPolicy, tools: dict[tuple[str, str], Callable[..., Any]]) -> None:
        self._policy = policy
        self._tools = tools

    def execute(self, server_id: str, capability: str, arguments: dict[str, Any]) -> Any:
        self._policy.require(server_id, capability)
        tool = self._tools.get((server_id, capability))
        if tool is None:
            raise LookupError("MCP tool is not registered")
        return tool(**arguments)


class McpToolExecutor:
    def __init__(self, *, policy: ToolPolicy, clients: dict[str, McpClient]) -> None:
        self._policy = policy
        self._clients = clients

    def execute(self, server_id: str, capability: str, arguments: dict[str, Any]) -> Any:
        self._policy.require(server_id, capability)
        client = self._clients.get(server_id)
        if client is None:
            raise LookupError("MCP server is not connected")
        return client.call_tool(capability, arguments)
