import pytest

from apps.api.app.models.gateway import TextGeneration
from apps.api.app.projects.html_dispatcher import HtmlModelDispatcher
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str]] = []

    def generate_text(self, organization_id: str, prompt: str) -> TextGeneration:
        self.calls.append((organization_id, prompt))
        return TextGeneration("fake", "fake-model", self.content)


def policy() -> AgentDispatchRequest:
    return AgentDispatchRequest("html", "text", True, True, True, True, False, "domestic", True)


pytestmark = pytest.mark.unit


def test_html_dispatcher_uses_organization_scoped_gateway_and_extracts_document() -> None:
    gateway = FakeGateway("说明文字\n```html\n<!doctype html><html><body><h1>海洋</h1></body></html>\n```")

    result = HtmlModelDispatcher(gateway).dispatch(policy(), "海洋主题", organization_id="org-001")

    assert result.html == "<!doctype html><html><body><h1>海洋</h1></body></html>"
    assert gateway.calls[0][0] == "org-001"
    assert "禁止使用 script" in gateway.calls[0][1]
    assert len(result.teaching_steps) == 3


def test_html_dispatcher_wraps_plain_text_as_safe_document() -> None:
    result = HtmlModelDispatcher(FakeGateway("你好 <script>alert(1)</script>")).dispatch(policy(), "问候页面", organization_id="org-001")

    assert result.html.startswith("<!doctype html>")
    assert "&lt;script&gt;" in result.html


def test_html_dispatcher_honors_dispatch_policy_before_model_call() -> None:
    gateway = FakeGateway("<html></html>")
    denied = AgentDispatchRequest("html", "text", False, True, True, True, False, "domestic", True)

    with pytest.raises(PermissionError, match="classroom is closed"):
        HtmlModelDispatcher(gateway).dispatch(denied, "网页", organization_id="org-001")

    assert gateway.calls == []
