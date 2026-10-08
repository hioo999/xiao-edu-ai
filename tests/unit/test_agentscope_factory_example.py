import pytest

from infra.agentscope_factory import AgentScopeBridge, _content_from_response, create_agent, system_prompt_for


pytestmark = pytest.mark.unit


def test_agentscope_bridge_normalizes_agent_response() -> None:
    class FakeMessage:
        content = [{"type": "text", "text": "太好了，我们开始吧！"}]

    class FakeAgent:
        async def reply(self, message):
            assert message == {"role": "user", "content": "做一个网页"}
            return FakeMessage()

    bridge = AgentScopeBridge("html-teacher", "html", FakeAgent(), lambda _name, prompt, **_kwargs: {"role": "user", "content": prompt})
    result = bridge.run("做一个网页")

    assert result["content"] == "太好了，我们开始吧！"
    assert result["teachingSteps"]


def test_content_from_response_accepts_text_and_content_blocks() -> None:
    assert _content_from_response("直接回复") == "直接回复"
    assert _content_from_response({"content": "字典回复"}) == "字典回复"
    assert _content_from_response([{"type": "text", "text": "第一句"}, {"type": "text", "text": "第二句"}]) == "第一句\n第二句"


def test_agentscope_system_prompt_includes_enabled_skill_instructions() -> None:
    prompt = system_prompt_for("writing-coach", "text", ["先表扬学生。"])

    assert "写作小老师" in prompt
    assert "先表扬学生。" in prompt


def test_agentscope_factory_builds_a_current_sdk_agent_without_network_access(monkeypatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("AGENTSCOPE_MODEL_ID", "test-model")
    monkeypatch.setenv("AGENTSCOPE_BASE_URL", "https://example.invalid/v1")

    bridge = create_agent("writing-coach", capability="text", skill_instructions=["先鼓励学生。"])

    assert isinstance(bridge, AgentScopeBridge)
