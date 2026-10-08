from __future__ import annotations

from .catalog import KnowledgeCatalog


def build_grounded_prompt(catalog: KnowledgeCatalog | None, *, organization_id: str, course_id: str | None, prompt: str, max_documents: int = 4) -> str:
    if catalog is None:
        return prompt
    documents = catalog.search(organization_id, prompt, course_id=course_id)[:max_documents]
    if not documents:
        return prompt
    context = "\n\n".join(f"【{document.title}】\n{document.content}" for document in documents if document.content.strip())
    if not context:
        return prompt
    return f"请优先参考以下已授权教学资料；资料未涉及的内容不要编造来源。\n\n{context}\n\n学生问题：{prompt}"
