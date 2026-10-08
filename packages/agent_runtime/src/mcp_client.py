from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import itertools
import json
import os
import subprocess

import httpx


class JsonRpcTransport(Protocol):
    def request(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class McpTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] | None = None


class McpProtocolError(RuntimeError):
    pass


class HttpJsonRpcTransport:
    def __init__(self, url: str, *, headers: dict[str, str] | None = None, timeout: float = 20.0) -> None:
        self._client = httpx.Client(base_url=url, headers=headers, timeout=timeout, trust_env=False)

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post("", json=payload)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise McpProtocolError("MCP JSON-RPC response must be an object")
        return body

    def close(self) -> None:
        self._client.close()


class StdioJsonRpcTransport:
    """Line-delimited JSON-RPC transport for an MCP server process.

    Commands originate from deployment configuration, never from API requests.
    """

    def __init__(self, command: str, args: list[str] | None = None, *, environment: dict[str, str] | None = None) -> None:
        if not command.strip():
            raise ValueError("MCP stdio command is required")
        self._process = subprocess.Popen(
            [command, *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, **(environment or {})},
        )

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._process.poll() is not None:
            raise McpProtocolError("MCP stdio server is not running")
        if self._process.stdin is None or self._process.stdout is None:
            raise McpProtocolError("MCP stdio pipes are unavailable")
        self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise McpProtocolError("MCP stdio server closed without a response")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise McpProtocolError("MCP stdio server returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise McpProtocolError("MCP JSON-RPC response must be an object")
        return response

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)


def build_mcp_clients_from_env(raw_config: str | None = None) -> dict[str, "McpClient"]:
    """Build deployment-configured MCP clients without exposing endpoints to users."""
    raw = raw_config if raw_config is not None else os.getenv("MCP_SERVER_CONNECTIONS", "[]")
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("MCP_SERVER_CONNECTIONS must be a JSON list") from exc
    if not isinstance(entries, list):
        raise ValueError("MCP_SERVER_CONNECTIONS must be a JSON list")
    clients: dict[str, McpClient] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"].strip():
            raise ValueError("each MCP server needs a non-empty id")
        server_id, transport = entry["id"], entry.get("transport", "http")
        if server_id in clients:
            raise ValueError("MCP server ids must be unique")
        if transport == "http":
            url = entry.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                raise ValueError("HTTP MCP server needs an http(s) url")
            headers = entry.get("headers", {})
            if not isinstance(headers, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in headers.items()):
                raise ValueError("MCP HTTP headers must be string pairs")
            clients[server_id] = McpClient(HttpJsonRpcTransport(url, headers=headers))
        elif transport == "stdio":
            command, args = entry.get("command"), entry.get("args", [])
            if not isinstance(command, str) or not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise ValueError("stdio MCP server needs a command and string args")
            clients[server_id] = McpClient(StdioJsonRpcTransport(command, args))
        else:
            raise ValueError("MCP transport must be http or stdio")
    return clients


class McpClient:
    """Small MCP JSON-RPC client; transport is injected for HTTP or stdio deployments."""

    def __init__(self, transport: JsonRpcTransport) -> None:
        self._transport = transport
        self._ids = itertools.count(1)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request = {"jsonrpc": "2.0", "id": next(self._ids), "method": method}
        if params is not None:
            request["params"] = params
        response = self._transport.request(request)
        if response.get("error"):
            error = response["error"]
            raise McpProtocolError(str(error.get("message", "MCP request failed")))
        result = response.get("result")
        if not isinstance(result, dict):
            raise McpProtocolError("MCP response result must be an object")
        return result

    def initialize(self, *, protocol_version: str = "2025-06-18") -> dict[str, Any]:
        return self._request("initialize", {"protocolVersion": protocol_version, "capabilities": {}, "clientInfo": {"name": "xiao-edu-ai", "version": "1.0"}})

    def list_tools(self) -> list[McpTool]:
        result = self._request("tools/list")
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise McpProtocolError("MCP tools must be a list")
        parsed: list[McpTool] = []
        for item in tools:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise McpProtocolError("MCP tool must contain a name")
            parsed.append(McpTool(item["name"], item.get("description", ""), item.get("inputSchema")))
        return parsed

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if "isError" in result and result["isError"] is True:
            raise McpProtocolError("MCP tool returned an error")
        return result.get("structuredContent", result.get("content", result))
