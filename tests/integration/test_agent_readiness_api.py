import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def test_agent_readiness_endpoint_reports_safe_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTSCOPE_AGENT_FACTORY", raising=False)
    response = TestClient(create_app()).get("/health/agents")
    assert response.status_code == 200
    assert response.json()["mode"] == "gateway"


def test_agent_readiness_reports_missing_agentscope_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_AGENT_FACTORY", "infra.agentscope_factory:create_agent")
    monkeypatch.delenv("AGENTSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("AGENTSCOPE_MODEL_ID", raising=False)

    payload = TestClient(create_app()).get("/health/agents").json()

    assert payload["mode"] == "agentscope"
    assert payload["ready"] is False
    assert payload["reason"] == "AgentScope API Key or model ID is not configured"
    assert {check["id"] for check in payload["checks"]} >= {"factory", "sdk", "apiKey", "model"}


def test_agent_readiness_accepts_a_complete_agentscope_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSCOPE_AGENT_FACTORY", "infra.agentscope_factory:create_agent")
    monkeypatch.setenv("AGENTSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("AGENTSCOPE_MODEL_ID", "test-model")
    monkeypatch.setenv("AGENTSCOPE_MCP_SERVERS", "[]")

    payload = TestClient(create_app()).get("/health/agents").json()

    assert payload["ready"] is True
    assert payload["reason"] == "ready"
