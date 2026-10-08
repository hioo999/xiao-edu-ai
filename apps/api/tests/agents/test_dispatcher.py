from packages.agent_runtime.src.dispatcher import AgentDispatcher, AgentExecutionResult
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest


class FakeExecutor:
    def execute(self, agent_kind: str, prompt: str) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_kind=agent_kind,
            html="<main>生成结果</main>",
            teaching_steps=[f"围绕“{prompt}”确定主题"],
        )


def test_dispatcher_keeps_business_layer_independent_from_executor() -> None:
    request = AgentDispatchRequest(
        agent_kind="html",
        capability="text",
        classroom_open=True,
        feature_enabled=True,
        quota_available=True,
        model_available=True,
        allow_foreign=False,
        model_region="domestic",
        mcp_approved=True,
    )

    result = AgentDispatcher(FakeExecutor()).dispatch(request, "做一个海底世界网页")

    assert result.html == "<main>生成结果</main>"
    assert result.teaching_steps == ["围绕“做一个海底世界网页”确定主题"]
