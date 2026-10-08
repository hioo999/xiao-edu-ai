import pytest

from apps.api.app.agents.runtime import GatewayAgentRuntime, build_agent_runtime
from apps.api.app.models.gateway import TextGeneration


pytestmark = pytest.mark.unit


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompt = ""

    def generate_text(self, organization_id: str, prompt: str) -> TextGeneration:
        self.prompt = prompt
        return TextGeneration("fake", "fake", self.content)


def test_gateway_agent_runtime_executes_text_agent() -> None:
    gateway = FakeGateway("这是你的故事开头。")

    result = GatewayAgentRuntime(gateway).execute(agent_id="writing-coach", capability="text", organization_id="org-001", prompt="写一个海洋故事")

    assert "小学 AI 创作课" in gateway.prompt
    assert "这是你的故事开头" in result.html
    assert result.agent_kind == "writing-coach"


def test_gateway_agent_runtime_keeps_html_output_for_web_agent() -> None:
    result = GatewayAgentRuntime(FakeGateway("<html><body>海洋</body></html>")).execute(agent_id="web-coach", capability="html", organization_id="org-001", prompt="做网页")

    assert result.html == "<html><body>海洋</body></html>"


def test_build_agent_runtime_uses_gateway_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTSCOPE_AGENT_FACTORY", raising=False)

    runtime = build_agent_runtime(FakeGateway("内容"))

    assert isinstance(runtime, GatewayAgentRuntime)


@pytest.mark.parametrize("factory_path", ["factory", "module:", ":factory"])
def test_build_agent_runtime_rejects_invalid_factory_path(monkeypatch: pytest.MonkeyPatch, factory_path: str) -> None:
    monkeypatch.setenv("AGENTSCOPE_AGENT_FACTORY", factory_path)

    with pytest.raises(RuntimeError, match="package.module:factory"):
        build_agent_runtime(FakeGateway("内容"))
