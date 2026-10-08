import json

import pytest

from packages.agent_runtime.src.mcp_client import McpClient, McpProtocolError, StdioJsonRpcTransport, build_mcp_clients_from_env
from packages.agent_runtime.src.tool_policy import McpServer, McpToolExecutor, ToolPolicy


class FakeTransport:
    def __init__(self):
        self.requests = []

    def request(self, payload):
        self.requests.append(payload)
        if payload["method"] == "initialize":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"capabilities": {}}}
        if payload["method"] == "tools/list":
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": [{"name": "search", "description": "搜索"}]}}
        return {"jsonrpc": "2.0", "id": payload["id"], "result": {"structuredContent": {"items": [payload["params"]["arguments"]]}}}


def test_mcp_client_initializes_discovers_and_calls_tool():
    transport = FakeTransport()
    client = McpClient(transport)

    assert client.initialize()["capabilities"] == {}
    assert client.list_tools()[0].name == "search"
    assert client.call_tool("search", {"query": "校园"}) == {"items": [{"query": "校园"}]}
    assert [request["method"] for request in transport.requests] == ["initialize", "tools/list", "tools/call"]


def test_mcp_error_response_is_rejected():
    class ErrorTransport:
        def request(self, payload):
            return {"jsonrpc": "2.0", "id": payload["id"], "error": {"message": "denied"}}

    with pytest.raises(McpProtocolError, match="denied"):
        McpClient(ErrorTransport()).list_tools()


def test_mcp_tool_executor_applies_policy_before_remote_call():
    transport = FakeTransport()
    executor = McpToolExecutor(
        policy=ToolPolicy(servers=[McpServer("school", True, {"search"})]),
        clients={"school": McpClient(transport)},
    )

    assert executor.execute("school", "search", {"query": "树"})["items"]
    with pytest.raises(PermissionError):
        McpToolExecutor(policy=ToolPolicy(servers=[McpServer("school", False, {"search"})]), clients={"school": McpClient(transport)}).execute("school", "search", {})


def test_stdio_transport_sends_line_delimited_json_and_reads_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class Pipe:
        def __init__(self, response=""):
            self.written = ""
            self.response = response

        def write(self, value): self.written += value
        def flush(self): pass
        def readline(self): return self.response

    class Process:
        def __init__(self):
            self.stdin = Pipe()
            self.stdout = Pipe('{"jsonrpc":"2.0","id":1,"result":{}}\n')
            self.stderr = Pipe()
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout): pass

    process = Process()
    monkeypatch.setattr("packages.agent_runtime.src.mcp_client.subprocess.Popen", lambda *_args, **_kwargs: process)
    transport = StdioJsonRpcTransport("trusted-mcp", ["--serve"])

    assert transport.request({"id": 1}) == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert json.loads(process.stdin.written) == {"id": 1}


def test_connection_factory_validates_deployment_config(monkeypatch: pytest.MonkeyPatch) -> None:
    config = '[{"id":"school-search","transport":"http","url":"https://mcp.example.test"}]'
    clients = build_mcp_clients_from_env(config)
    assert set(clients) == {"school-search"}

    with pytest.raises(ValueError, match="JSON list"):
        build_mcp_clients_from_env("{}")
    with pytest.raises(ValueError, match="http\\(s\\) url"):
        build_mcp_clients_from_env('[{"id":"bad","transport":"http","url":"file:///tmp/x"}]')
    with pytest.raises(ValueError, match="command"):
        build_mcp_clients_from_env('[{"id":"bad","transport":"stdio","args":[]}]')
