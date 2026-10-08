from apps.api.app.agents.expert_teams import ExpertTeam, run_expert_team


def test_expert_team_runs_fixed_roles_and_aggregates_output() -> None:
    team = ExpertTeam(
        name="网页创作小队",
        roles=("策划员", "设计师", "检查员"),
    )

    result = run_expert_team(team, "做一个校园植物网页")

    assert result["team"] == "网页创作小队"
    assert result["roles"] == ["策划员", "设计师", "检查员"]
    assert "校园植物网页" in result["summary"]
