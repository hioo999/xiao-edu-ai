from apps.api.app.moderation.service import ModerationDecision, ModerationService


def test_classroom_policy_blocks_disallowed_input() -> None:
    service = ModerationService(blocked_terms={"危险词"})

    decision = service.check("这是危险词", mode="classroom")

    assert decision is ModerationDecision.BLOCKED


def test_free_creation_policy_allows_non_blocked_input() -> None:
    service = ModerationService(blocked_terms={"危险词"})

    assert service.check("做一个植物网页", mode="free") is ModerationDecision.ALLOWED
