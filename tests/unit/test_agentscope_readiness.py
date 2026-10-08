import pytest

from apps.api.app.agents.runtime import agentscope_readiness


pytestmark = pytest.mark.unit


def test_agentscope_readiness_reports_gateway_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTSCOPE_AGENT_FACTORY", raising=False)
    assert agentscope_readiness()["mode"] == "gateway"


def test_agentscope_readiness_rejects_invalid_mcp_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_AGENT_FACTORY", "app.agents:factory")
    monkeypatch.setenv("AGENTSCOPE_MCP_SERVERS", "not-json")
    status = agentscope_readiness()
    assert status["ready"] is False
    assert "JSON" in status["reason"]
