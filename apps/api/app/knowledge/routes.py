from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from .catalog import KnowledgeCatalog
from .scopes import KnowledgeScope

class KnowledgeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(default="", max_length=100_000)
    scope: KnowledgeScope = KnowledgeScope.ORGANIZATION
    scopeId: str | None = None

def create_knowledge_router(auth: AuthService, catalog: KnowledgeCatalog) -> APIRouter:
    router = APIRouter(prefix="/knowledge", tags=["knowledge"])
    admin = require_role(require_session(auth), "platform_admin", "organization_admin", "teacher")
    @router.get("")
    def list_documents(session: SessionContext = Depends(admin)) -> dict[str, object]:
        return {"documents": [document.__dict__ for document in catalog.list(session.organization_id)]}
    @router.post("")
    def add_document(request: KnowledgeRequest, session: SessionContext = Depends(admin)) -> dict[str, object]:
        if request.scope is KnowledgeScope.PLATFORM and session.role != "platform_admin":
            raise HTTPException(status_code=403, detail="platform scope requires platform admin")
        scope_id = request.scopeId or session.organization_id
        if request.scope is KnowledgeScope.ORGANIZATION and session.role != "platform_admin" and scope_id != session.organization_id:
            raise HTTPException(status_code=403, detail="knowledge scope belongs to another organization")
        organization_id = None if session.role == "platform_admin" and request.scope is KnowledgeScope.PLATFORM else session.organization_id
        return catalog.add(request.scope, scope_id, request.title, organization_id, request.content).__dict__
    @router.get("/search")
    def search_documents(query: str, courseId: str | None = None, session: SessionContext = Depends(admin)) -> dict[str, object]:
        documents = catalog.search(session.organization_id, query, course_id=courseId)
        return {"documents": [document.__dict__ for document in documents]}
    @router.delete("/{document_id}")
    def delete_document(document_id: str, session: SessionContext = Depends(admin)) -> dict[str, str]:
        try:
            catalog.delete(document_id, session.organization_id, platform_admin=session.role == "platform_admin")
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="knowledge document access denied") from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="knowledge document not found") from exc
        return {"documentId": document_id, "status": "deleted"}
    return router
