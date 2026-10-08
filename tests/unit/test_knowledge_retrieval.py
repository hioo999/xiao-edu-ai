import pytest

from apps.api.app.inspiration.catalog import InspirationCatalog
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.knowledge.retrieval import build_grounded_prompt
from apps.api.app.knowledge.scopes import KnowledgeScope


pytestmark = pytest.mark.unit


def test_retrieval_adds_only_authorized_matching_knowledge(tmp_path) -> None:
    catalog = KnowledgeCatalog(tmp_path / "knowledge.db")
    catalog.add(KnowledgeScope.ORGANIZATION, "org-001", "海洋课堂资料", "org-001", "海洋网页可以使用蓝色和珊瑚色。")
    catalog.add(KnowledgeScope.ORGANIZATION, "org-002", "其他机构资料", "org-002", "不应被读取。")

    grounded = build_grounded_prompt(catalog, organization_id="org-001", course_id=None, prompt="怎样做海洋网页？")

    assert "海洋课堂资料" in grounded
    assert "不应被读取" not in grounded
    assert grounded.endswith("学生问题：怎样做海洋网页？")


def test_retrieval_leaves_prompt_unchanged_without_matching_knowledge(tmp_path) -> None:
    catalog = KnowledgeCatalog(tmp_path / "knowledge.db")

    assert build_grounded_prompt(catalog, organization_id="org-001", course_id=None, prompt="做一个太空网页") == "做一个太空网页"
