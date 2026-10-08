from packages.agent_runtime.src.agentscope_executor import AgentScopeExecutor


class FakeAgent:
    def run(self, prompt: str) -> dict[str, object]:
        return {"html": f"<main>{prompt}</main>", "teachingSteps": ["观察页面结构"]}


def test_agentscope_executor_normalizes_runtime_output() -> None:
    executor = AgentScopeExecutor(lambda agent_kind: FakeAgent())

    result = executor.execute("html", "做一个校园网页")

    assert result.agent_kind == "html"
    assert result.html == "<main>做一个校园网页</main>"
    assert result.teaching_steps == ["观察页面结构"]


def test_agentscope_executor_injects_tool_executor_into_compatible_factory() -> None:
    class ToolAwareAgent:
        def __init__(self, tool_executor) -> None:
            self.tool_executor = tool_executor

        def run(self, prompt: str) -> dict[str, object]:
            return {"html": f"<main>{self.tool_executor.execute('school', 'search', {'query': prompt})}</main>", "teachingSteps": []}

    class ToolExecutor:
        def execute(self, server_id, capability, arguments):
            assert (server_id, capability) == ("school", "search")
            return arguments["query"]

    executor = AgentScopeExecutor(lambda _agent_id, tool_executor: ToolAwareAgent(tool_executor), ToolExecutor())

    assert "找资料" in executor.execute("web-coach", "找资料").html


def test_agentscope_executor_awaits_async_reply_and_passes_runtime_context() -> None:
    class AsyncAgent:
        async def reply(self, prompt: str) -> str:
            return f"完成：{prompt}"

    seen: dict[str, str] = {}

    def factory(agent_id: str, *, organization_id: str, capability: str):
        seen.update({"agent_id": agent_id, "organization_id": organization_id, "capability": capability})
        return AsyncAgent()

    result = AgentScopeExecutor(factory).execute("writing-coach", "写故事", organization_id="org-001", capability="text")

    assert "完成：写故事" in result.html
    assert seen == {"agent_id": "writing-coach", "organization_id": "org-001", "capability": "text"}


def test_agentscope_executor_passes_enabled_skill_instructions_to_factory() -> None:
    class FakeAgent:
        def run(self, _prompt: str) -> dict[str, object]:
            return {"content": "完成", "teachingSteps": []}

    seen: dict[str, object] = {}

    def factory(_agent_id: str, *, skill_instructions: list[str]):
        seen["skills"] = skill_instructions
        return FakeAgent()

    AgentScopeExecutor(factory).execute("writing-coach", "写故事", skill_instructions=["先表扬学生。"])

    assert seen["skills"] == ["先表扬学生。"]
