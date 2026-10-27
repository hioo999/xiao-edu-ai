from packages.agent_runtime.src.dispatcher import AgentExecutionResult
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest

from apps.api.app.projects.html_service import HtmlWorkspaceService
from apps.api.app.projects.html_dispatcher import DESIGN_AGENT_PROTOCOL


def test_design_agent_protocol_requires_eight_dimension_self_review() -> None:
    for dimension in ("字体排版", "留白节奏", "视觉层级", "色彩系统", "动效", "微交互", "响应式布局", "原创性"):
        assert dimension in DESIGN_AGENT_PROTOCOL
    assert "反复迭代" in DESIGN_AGENT_PROTOCOL
    assert "最多进行 3 轮修订" in DESIGN_AGENT_PROTOCOL


class FakeDispatcher:
    def dispatch(self, request: AgentDispatchRequest, prompt: str, *, organization_id: str) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent_kind="html",
            html=f"<main>{prompt}</main>",
            teaching_steps=["先确定页面主题", "再检查互动按钮"],
        )


def test_html_service_dispatches_and_saves_sanitized_version() -> None:
    service = HtmlWorkspaceService(FakeDispatcher())

    project = service.generate(
        project_id="project-001",
        owner_user_id="student-001",
        organization_id="org-001",
        prompt="做一个海底世界网页",
        policy=AgentDispatchRequest(
            agent_kind="html",
            capability="text",
            classroom_open=True,
            feature_enabled=True,
            quota_available=True,
            model_available=True,
            allow_foreign=False,
            model_region="domestic",
            mcp_approved=True,
        ),
    )

    assert project.current_version_id == "project-001-v1"
    assert project.versions[0].html == "<main>做一个海底世界网页</main>"
    assert project.versions[0].teaching_steps[0] == "先确定页面主题"
