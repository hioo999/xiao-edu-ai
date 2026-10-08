from apps.api.app.agents.catalog import AgentCatalog, ManagedAgent, ManagedTool


def test_catalog_filters_custom_agents_and_tools_by_organization(tmp_path) -> None:
    catalog = AgentCatalog(tmp_path / "platform.db")
    catalog.save_agent(ManagedAgent("org-one-agent", "一号智能体", "text", "3-6", True, "org-001"))
    catalog.save_agent(ManagedAgent("org-two-agent", "二号智能体", "text", "3-6", True, "org-002"))
    catalog.save(ManagedTool("org-one-skill", "skill", "一号技能", "text", True, "org-001"))

    assert [agent.agent_id for agent in catalog.list_agents("org-001")] == ["org-one-agent"]
    assert [tool.tool_id for tool in catalog.list("skill", "org-001")] == ["org-one-skill"]
    assert catalog.list_agents("org-002")[0].agent_id == "org-two-agent"


def test_catalog_persists_skill_instruction(tmp_path) -> None:
    database = tmp_path / "platform.db"
    AgentCatalog(database).save(ManagedTool("writing-guide", "skill", "写作规则", "text", True, "org-001", "先提出一个启发性问题。"))

    restored = AgentCatalog(database).list("skill", "org-001")

    assert restored[0].instruction == "先提出一个启发性问题。"
