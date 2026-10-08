from dataclasses import dataclass
from enum import StrEnum


class KnowledgeScope(StrEnum):
    PLATFORM = "platform"
    ORGANIZATION = "organization"
    COURSE = "course"
    TEACHER = "teacher"
    STUDENT = "student"


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    scope: KnowledgeScope
    scope_id: str
    title: str
    organization_id: str | None = None
    content: str = ""


def resolve_documents(
    documents: list[KnowledgeDocument], *, organization_id: str, course_id: str | None
) -> list[KnowledgeDocument]:
    result: list[KnowledgeDocument] = []
    for document in documents:
        if document.scope is KnowledgeScope.PLATFORM:
            result.append(document)
        elif document.scope is KnowledgeScope.ORGANIZATION:
            if document.scope_id != organization_id:
                raise PermissionError("knowledge document belongs to another organization")
            result.append(document)
        elif document.scope is KnowledgeScope.COURSE and course_id and document.scope_id == course_id:
            result.append(document)
    return result
