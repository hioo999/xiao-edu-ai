from dataclasses import replace

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.core.scanning import UnsafeUploadError, build_upload_scanner, scan_upload
from apps.api.app.projects.artifact_storage import WorkArtifactStore

from .catalog import InspirationCatalog
from .models import InspirationCase
from .recommender import recommend_cases


class InspirationCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    gradeMin: int = Field(ge=3, le=6)
    gradeMax: int = Field(ge=3, le=6)
    interests: list[str] = Field(min_length=1, max_length=12)
    difficulty: str = Field(pattern="^(入门|进阶|挑战)$")
    durationMinutes: int = Field(ge=5, le=180)
    prompt: str = Field(min_length=1, max_length=2000)
    capability: str = Field(pattern="^(text|html|image|music|video)$")
    organizationIds: list[str] = Field(default_factory=list)


class FavoriteRequest(BaseModel):
    enabled: bool = True


def case_payload(case: InspirationCase, *, favorite: bool = False) -> dict[str, object]:
    return {"caseId": case.case_id, "title": case.title, "gradeRange": list(case.grade_range), "interests": sorted(case.interests), "difficulty": case.difficulty, "durationMinutes": case.duration_minutes, "prompt": case.prompt, "capability": case.capability, "favorite": favorite, "attachmentId": case.attachment_id, "attachmentFilename": case.attachment_filename}


def create_inspiration_router(auth_service: AuthService, catalog: InspirationCatalog, audit_log: AuditLog | None = None, artifact_store: WorkArtifactStore | None = None) -> APIRouter:
    router = APIRouter(prefix="/inspiration", tags=["inspiration"])
    session_dependency = require_session(auth_service)
    admin_dependency = require_role(session_dependency, "platform_admin", "organization_admin", "teacher")
    attachments = artifact_store or WorkArtifactStore("var/work-artifacts")
    upload_scanner = build_upload_scanner()

    @router.get("")
    def list_cases(grade: int = Query(default=4, ge=3, le=6), interests: str = "", session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        cases = catalog.list_visible(session.organization_id)
        interest_set = {item.strip() for item in interests.split(",") if item.strip()}
        if interest_set:
            cases = recommend_cases(cases, organization_id=session.organization_id, grade=grade, interests=interest_set)
        favorites = catalog.favorites_for(session.user_id, session.organization_id)
        return {"cases": [case_payload(case, favorite=case.case_id in favorites) for case in cases]}

    @router.post("")
    def save_case(request: InspirationCaseRequest, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        if request.gradeMin > request.gradeMax:
            raise HTTPException(status_code=422, detail="grade range is invalid")
        organizations = set(request.organizationIds) if session.role == "platform_admin" else {session.organization_id}
        case = catalog.create(title=request.title.strip(), grade_range=(request.gradeMin, request.gradeMax), interests={item.strip() for item in request.interests if item.strip()}, difficulty=request.difficulty, duration_minutes=request.durationMinutes, prompt=request.prompt.strip(), capability=request.capability, organization_ids=organizations)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="inspiration.saved", target_type="inspiration_case", target_id=case.case_id)
        return case_payload(case)

    @router.post("/import")
    async def import_case(
        title: str = Form(...), prompt: str = Form(...), capability: str = Form("html"), grade_min: int = Form(3), grade_max: int = Form(6),
        difficulty: str = Form("入门"), duration_minutes: int = Form(20), interests: str = Form("创意"), file: UploadFile | None = File(default=None),
        session: SessionContext = Depends(admin_dependency),
    ) -> dict[str, object]:
        if capability not in {"text", "html", "image", "music", "video"} or difficulty not in {"入门", "进阶", "挑战"} or not 3 <= grade_min <= grade_max <= 6:
            raise HTTPException(status_code=422, detail="invalid inspiration metadata")
        case = catalog.create(title=title.strip(), grade_range=(grade_min, grade_max), interests={item.strip() for item in interests.split(",") if item.strip()} or {"创意"}, difficulty=difficulty, duration_minutes=duration_minutes, prompt=prompt.strip(), capability=capability, organization_ids={session.organization_id})
        if file:
            content = await file.read()
            if not content or len(content) > 50 * 1024 * 1024:
                raise HTTPException(status_code=422, detail="attachment is empty or exceeds 50MB")
            try:
                scan_upload(upload_scanner, content)
            except UnsafeUploadError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            artifact = attachments.save(case.case_id, session.organization_id, file.filename or "inspiration-resource", file.content_type or "application/octet-stream", content)
            case = catalog.save(replace(case, attachment_id=artifact.asset_id, attachment_filename=artifact.filename))
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="inspiration.imported", target_type="inspiration_case", target_id=case.case_id)
        return case_payload(case)

    @router.get("/{case_id}/attachment")
    def download_attachment(case_id: str, session: SessionContext = Depends(session_dependency)) -> Response:
        visible = {case.case_id: case for case in catalog.list_visible(session.organization_id)}
        case = visible.get(case_id)
        if case is None or not case.attachment_id:
            raise HTTPException(status_code=404, detail="inspiration attachment not found")
        try:
            artifact = attachments.get(case.attachment_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="inspiration attachment not found") from exc
        return Response(attachments.read(artifact), media_type=artifact.content_type, headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'})

    @router.post("/{case_id}/favorite")
    def favorite_case(case_id: str, request: FavoriteRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        try:
            catalog.favorite(case_id, session.user_id, session.organization_id, request.enabled)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="inspiration case not found") from exc
        return {"caseId": case_id, "favorite": request.enabled}

    @router.delete("/{case_id}")
    def delete_case(case_id: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, str]:
        if session.role != "platform_admin":
            visible_ids = {case.case_id for case in catalog.list_visible(session.organization_id)}
            if case_id not in visible_ids:
                raise HTTPException(status_code=404, detail="inspiration case not found")
        try:
            catalog.delete(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="inspiration case not found") from exc
        return {"caseId": case_id, "status": "deleted"}

    return router
