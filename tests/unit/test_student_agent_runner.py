import json
import sys
from types import SimpleNamespace, ModuleType

from cryptography.fernet import Fernet
import pytest

from apps.api.app.agents.catalog import AgentCatalog, ManagedTool, StudentAgent
from apps.api.app.agents.student_runner import StudentAgentRunner
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.models.gateway import TextGeneration
from apps.api.app.models.registry import ModelCapability, ModelProvider, ProviderRegistry, SecretVault
from packages.agent_runtime.src.mcp_client import McpTool


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.prompts = []

    def generate_text(self, organization_id, prompt, **options):
        self.prompts.append(prompt)
        assert options["provider_id"] == "selected"
        return TextGeneration("selected", "test", next(self.replies))


class Client:
    def __init__(self):
        self.calls = []

    def initialize(self):
        return {}

    def list_tools(self):
        return [McpTool("search", "查找课堂资料", {"type": "object"})]

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"result": "月球花园有蓝色花朵"}


def setup_runner(monkeypatch, replies):
    monkeypatch.setenv("MCP_SERVER_CONNECTIONS", json.dumps([{"id": "library", "url": "http://example.invalid"}]))
    catalog = AgentCatalog()
    catalog.save(ManagedTool("library", "mcp", "图书工具", "search", True, "school"))
    registry = ProviderRegistry(SecretVault(Fernet.generate_key()))
    registry.register(ModelProvider("selected", "school", ModelCapability.TEXT, "domestic", 1, "private-test-key", model_id="test-model"))
    client = Client()
    model = Model(replies)
    runner = StudentAgentRunner(model, registry, catalog, KnowledgeCatalog(), lambda raw: {"library": client})
    session = SimpleNamespace(organization_id="school", user_id="student")
    agent = StudentAgent("agent", "school", "student", "图书助手", "", "通用", "先查资料再写故事", "selected")
    configuration = {"capability": "text", "skillIds": [], "mcpIds": ["library"], "knowledgeIds": [], "runtime": "gateway"}
    return runner, session, agent, configuration, model, client


def test_runner_executes_authorized_mcp_and_uses_result(monkeypatch):
    action = json.dumps({"tool": {"serverId": "library", "name": "search", "arguments": {"query": "花园"}}})
    runner, session, agent, settings, model, client = setup_runner(monkeypatch, [action, "花园故事完成了。"])
    assert runner.run(session, agent, settings, [], "写故事") == "花园故事完成了。"
    assert client.calls == [("search", {"query": "花园"})]
    assert "月球花园有蓝色花朵" in model.prompts[-1]


def test_runner_refuses_a_model_request_for_an_unapproved_tool(monkeypatch):
    action = json.dumps({"tool": {"serverId": "library", "name": "delete_all", "arguments": {}}})
    runner, session, agent, settings, model, client = setup_runner(monkeypatch, [action])
    with pytest.raises(PermissionError):
        runner.run(session, agent, settings, [], "写故事")
    assert client.calls == []


def test_agentscope_receives_saved_instructions_and_selected_model(monkeypatch):
    runner, session, agent, settings, model, client = setup_runner(monkeypatch, [])
    captured = {}
    module = ModuleType("test_student_factory")
    def factory(agent_id, **context):
        captured.update(context)
        return SimpleNamespace(run=lambda prompt: {"content": "使用所选模型完成了故事"})
    module.factory = factory
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv("AGENTSCOPE_AGENT_FACTORY", "test_student_factory:factory")
    settings.update(runtime="agentscope", mcpIds=[])
    result = runner.run(session, agent, settings, [], "写故事")
    assert result == "使用所选模型完成了故事"
    assert captured["model_config"]["model_id"] == "test-model"
    assert captured["instructions"] == "先查资料再写故事"
    assert "private-test-key" not in result
