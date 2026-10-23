from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.courses.catalog import CourseCatalog
from .catalog import KnowledgeCatalog
from .scopes import KnowledgeScope

class KnowledgeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(default="", max_length=100_000)
    scope: KnowledgeScope = KnowledgeScope.ORGANIZATION
    scopeId: str | None = None

def create_knowledge_router(auth: AuthService, catalog: KnowledgeCatalog, classrooms: AssistanceManager | None = None, courses: CourseCatalog | None = None) -> APIRouter:
    router = APIRouter(prefix="/knowledge", tags=["knowledge"])
    admin = require_role(require_session(auth), "platform_admin", "organization_admin", "teacher")
    access = TeachingAccess(auth, classrooms)

    def scope_allowed(scope: KnowledgeScope, scope_id: str, session: SessionContext, *, write: bool = False) -> bool:
        if scope is KnowledgeScope.PLATFORM:
            return not write or session.role == "platform_admin"
        if scope is KnowledgeScope.ORGANIZATION:
            return scope_id == session.organization_id and (not write or session.role != "teacher")
        if scope in {KnowledgeScope.TEACHER, KnowledgeScope.STUDENT}:
            owner = auth.user_for_id(scope_id)
            expected_role = "teacher" if scope is KnowledgeScope.TEACHER else "student"
            if owner is None or owner.organization_id != session.organization_id or owner.role != expected_role:
                return False
            return session.role != "teacher" or (scope is KnowledgeScope.TEACHER and scope_id == session.user_id)
        if courses is None:
            return False
        try:
            course = courses.get(scope_id, session.organization_id)
        except (KeyError, PermissionError):
            return False
        if session.role != "teacher" or course.author_user_id == session.user_id:
            return True
        return not write and any(course.course_id == published.course_id for class_id in access.teacher_class_ids(session) for published in courses.list_for_class(class_id, session.organization_id))

    def document_allowed(document, session: SessionContext, *, write: bool = False) -> bool:
        if document.scope is not KnowledgeScope.PLATFORM and document.organization_id not in (None, session.organization_id):
            return False
        return scope_allowed(document.scope, document.scope_id, session, write=write)

    @router.get("")
    def list_documents(session: SessionContext = Depends(admin)) -> dict[str, object]:
        return {"documents": [document.__dict__ for document in catalog.list(session.organization_id) if document_allowed(document, session)]}
    @router.post("")
    def add_document(request: KnowledgeRequest, session: SessionContext = Depends(admin)) -> dict[str, object]:
        if request.scope is KnowledgeScope.PLATFORM and session.role != "platform_admin":
            raise HTTPException(status_code=403, detail="platform scope requires platform admin")
        scope_id = request.scopeId or session.organization_id
        if request.scope is KnowledgeScope.ORGANIZATION and session.role != "platform_admin" and scope_id != session.organization_id:
            raise HTTPException(status_code=403, detail="knowledge scope belongs to another organization")
        if not scope_allowed(request.scope, scope_id, session, write=True):
            raise HTTPException(status_code=403, detail="knowledge scope access denied")
        organization_id = None if session.role == "platform_admin" and request.scope is KnowledgeScope.PLATFORM else session.organization_id
        return catalog.add(request.scope, scope_id, request.title, organization_id, request.content).__dict__
    @router.get("/search")
    def search_documents(query: str, courseId: str | None = None, session: SessionContext = Depends(admin)) -> dict[str, object]:
        documents = catalog.search(session.organization_id, query, course_id=courseId)
        return {"documents": [document.__dict__ for document in documents if document_allowed(document, session)]}
    @router.delete("/{document_id}")
    def delete_document(document_id: str, session: SessionContext = Depends(admin)) -> dict[str, str]:
        document = next((document for document in catalog.list(session.organization_id) if document.document_id == document_id), None)
        if document is None:
            raise HTTPException(status_code=404, detail="knowledge document not found")
        if not document_allowed(document, session, write=True):
            raise HTTPException(status_code=403, detail="knowledge document access denied")
        try:
            catalog.delete(document_id, session.organization_id, platform_admin=session.role == "platform_admin")
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="knowledge document access denied") from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="knowledge document not found") from exc
        return {"documentId": document_id, "status": "deleted"}
    return router
