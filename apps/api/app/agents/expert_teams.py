from dataclasses import dataclass


@dataclass(frozen=True)
class ExpertTeam:
    name: str
    roles: tuple[str, ...]


def run_expert_team(team: ExpertTeam, prompt: str) -> dict[str, object]:
    return {
        "team": team.name,
        "roles": list(team.roles),
        "summary": f"团队围绕“{prompt}”完成了分工协作。",
    }
