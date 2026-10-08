import pytest

from apps.api.app.knowledge.scopes import KnowledgeDocument, KnowledgeScope, resolve_documents


def test_course_scope_inherits_organization_documents() -> None:
    documents = [
        KnowledgeDocument("org-doc", KnowledgeScope.ORGANIZATION, "org-001", "课堂守则"),
        KnowledgeDocument("course-doc", KnowledgeScope.COURSE, "course-001", "网页课程资料"),
        KnowledgeDocument("other-doc", KnowledgeScope.COURSE, "course-002", "其他课程"),
    ]

    result = resolve_documents(documents, organization_id="org-001", course_id="course-001")

    assert [document.document_id for document in result] == ["org-doc", "course-doc"]


def test_other_organization_document_is_denied() -> None:
    document = KnowledgeDocument("private", KnowledgeScope.ORGANIZATION, "org-002", "私有资料")

    with pytest.raises(PermissionError):
        resolve_documents([document], organization_id="org-001", course_id=None)


def test_knowledge_search_matches_content_and_course_scope() -> None:
    documents = [
        KnowledgeDocument("org-doc", KnowledgeScope.ORGANIZATION, "org-001", "课堂守则", content="网页课堂要先观察结构"),
        KnowledgeDocument("course-doc", KnowledgeScope.COURSE, "course-001", "网页课程资料", content="使用卡片和按钮"),
        KnowledgeDocument("other-course", KnowledgeScope.COURSE, "course-002", "其他课程资料", content="使用卡片和按钮"),
    ]

    visible = [document for document in documents if document.scope is KnowledgeScope.ORGANIZATION or document.scope is KnowledgeScope.COURSE and document.scope_id == "course-001"]
    result = [document for document in visible if "按钮" in document.content]

    assert [document.document_id for document in result] == ["course-doc"]
