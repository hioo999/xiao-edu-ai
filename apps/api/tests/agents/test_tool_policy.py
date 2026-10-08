import pytest

from packages.agent_runtime.src.tool_policy import McpServer, ToolExecutor, ToolPolicy


def test_student_can_only_use_admin_approved_mcp_capability() -> None:
    policy = ToolPolicy(
        servers=[McpServer("approved", approved=True, capabilities={"search"})],
    )

    assert policy.can_use("approved", "search") is True
    assert policy.can_use("approved", "filesystem") is False


def test_unapproved_mcp_is_denied() -> None:
    policy = ToolPolicy(servers=[McpServer("draft", approved=False, capabilities={"search"})])

    with pytest.raises(PermissionError):
        policy.require("draft", "search")


def test_executor_calls_only_approved_registered_tool() -> None:
    policy = ToolPolicy(servers=[McpServer("approved", approved=True, capabilities={"search"})])
    executor = ToolExecutor(policy=policy, tools={("approved", "search"): lambda query: {"query": query}})

    assert executor.execute("approved", "search", {"query": "校园"}) == {"query": "校园"}


def test_executor_rejects_unapproved_or_unregistered_tool() -> None:
    policy = ToolPolicy(servers=[McpServer("draft", approved=False, capabilities={"search"})])
    executor = ToolExecutor(policy=policy, tools={})

    with pytest.raises(PermissionError):
        executor.execute("draft", "search", {})

    approved = ToolExecutor(policy=ToolPolicy(servers=[McpServer("approved", True, {"search"})]), tools={})
    with pytest.raises(LookupError):
        approved.execute("approved", "search", {})
