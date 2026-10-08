from apps.api.app.inspiration.models import InspirationCase
from apps.api.app.inspiration.recommender import recommend_cases


def test_recommendation_prioritizes_grade_and_interest() -> None:
    cases = [
        InspirationCase(
            case_id="space-poster",
            title="做一张太空海报",
            grade_range=(3, 6),
            interests={"science"},
            difficulty="beginner",
            duration_minutes=30,
            approved_organization_ids={"org-001"},
        ),
        InspirationCase(
            case_id="music-story",
            title="给故事配音乐",
            grade_range=(4, 6),
            interests={"music"},
            difficulty="intermediate",
            duration_minutes=40,
            approved_organization_ids={"org-001"},
        ),
    ]

    result = recommend_cases(cases, organization_id="org-001", grade=4, interests={"science"})

    assert result[0].case_id == "space-poster"


def test_unapproved_case_is_not_recommended() -> None:
    case = InspirationCase(
        case_id="private-case",
        title="未审核案例",
        grade_range=(3, 6),
        interests={"science"},
        difficulty="beginner",
        duration_minutes=20,
        approved_organization_ids={"org-002"},
    )

    assert recommend_cases([case], organization_id="org-001", grade=4, interests={"science"}) == []
