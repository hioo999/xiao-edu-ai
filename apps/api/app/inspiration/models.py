from dataclasses import dataclass, field


@dataclass(frozen=True)
class InspirationCase:
    case_id: str
    title: str
    grade_range: tuple[int, int]
    interests: set[str]
    difficulty: str
    duration_minutes: int
    approved_organization_ids: set[str] = field(default_factory=set)
    prompt: str = ""
    capability: str = "text"
    attachment_id: str = ""
    attachment_filename: str = ""
