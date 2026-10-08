from .models import InspirationCase


def recommend_cases(
    cases: list[InspirationCase],
    *,
    organization_id: str,
    grade: int,
    interests: set[str],
) -> list[InspirationCase]:
    scored: list[tuple[int, InspirationCase]] = []
    for case in cases:
        if organization_id not in case.approved_organization_ids:
            continue
        if not case.grade_range[0] <= grade <= case.grade_range[1]:
            continue
        score = len(case.interests & interests) * 10
        score += 2 if case.grade_range[0] <= grade <= case.grade_range[1] else 0
        scored.append((score, case))
    scored.sort(key=lambda item: (-item[0], item[1].case_id))
    return [case for _, case in scored]
