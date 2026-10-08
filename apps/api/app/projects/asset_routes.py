import os
import zipfile
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.settings.service import SettingsStore
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.core.scanning import UnsafeUploadError, build_upload_scanner, scan_upload
from .catalog import CreativeAsset, CreativeAssetCatalog
from .artifact_storage import WorkArtifactStore
from .interactions import WorkInteractionStore
from .deployments import DeploymentService, ZipProjectAnalyzer, deployment_payload
from .showcase_media import ShowcaseMediaStore


class CreateAssetRequest(BaseModel):
    projectId: str
    kind: str = Field(pattern="^(text|image|music|video|webpage|lesson|report)$")
    title: str = Field(min_length=1, max_length=120)
    previewUrl: str = ""
    prompt: str = ""


class ReviewAssetRequest(BaseModel):
    state: str = Field(pattern="^(pending|approved|rejected)$")
    featured: bool = False


class UpdateAssetMetadataRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    previewUrl: str | None = Field(default=None, max_length=2000)
    coverUrl: str | None = Field(default=None, max_length=2000)
    processSteps: list[str] | None = Field(default=None, max_length=8)
    gradeMin: int | None = Field(default=None, ge=3, le=6)
    gradeMax: int | None = Field(default=None, ge=3, le=6)
    visibility: str | None = Field(default=None, pattern="^(organization|private)$")
    isExample: bool | None = None


class PublishDeploymentRequest(BaseModel):
    previewUrl: str = Field(min_length=8, max_length=2000)


class BatchReviewRequest(BaseModel):
    assetIds: list[str] = Field(min_length=1, max_length=500)
    state: str = Field(pattern="^(approved|rejected)$")
    featured: bool = False


class InteractionRequest(BaseModel):
    body: str = Field(default="", max_length=2000)


class LikeRequest(BaseModel):
    enabled: bool = True


def create_asset_router(auth_service: AuthService, catalog: CreativeAssetCatalog, settings_store: SettingsStore | None = None, audit_log: AuditLog | None = None, classrooms: AssistanceManager | None = None, artifact_store: WorkArtifactStore | None = None, interactions: WorkInteractionStore | None = None, deployments: DeploymentService | None = None, showcase_media: ShowcaseMediaStore | None = None) -> APIRouter:
    router = APIRouter(prefix="/works", tags=["works"])
    session_dependency = require_session(auth_service)
    student_dependency = require_role(session_dependency, "student")
    creative_dependency = require_student_creative_access(student_dependency, settings_store, auth_service, classrooms) if settings_store else student_dependency
    uploads = artifact_store or WorkArtifactStore(os.getenv("WORK_ARTIFACT_STORAGE_PATH", "var/work-artifacts"))
    interaction_store = interactions or WorkInteractionStore(os.getenv("WORK_INTERACTION_STORAGE_PATH", "var/work-interactions"))
    deployment_service = deployments or DeploymentService(os.getenv("DEPLOYMENT_STORAGE_PATH", "var/deployments"))
    showcase_media_store = showcase_media or ShowcaseMediaStore(os.getenv("SHOWCASE_MEDIA_STORAGE_PATH", "var/showcase-media"))
    analyzer = ZipProjectAnalyzer()
    upload_scanner = build_upload_scanner()

    @router.post("")
    def create_asset(request: CreateAssetRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        if session.role == "student":
            creative_dependency(session)
        return asset_payload(catalog.create(project_id=request.projectId, organization_id=session.organization_id, owner_user_id=session.user_id, kind=request.kind, title=request.title, preview_url=request.previewUrl, prompt=request.prompt))

    @router.post("/upload")
    async def upload_external_work(
        file: UploadFile = File(...),
        title: str = Form(""),
        ownerUserId: str = Form(""),
        session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin")),
    ) -> dict[str, object]:
        filename = file.filename or "uploaded-work"
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in {"html", "htm", "zip"}:
            raise HTTPException(status_code=422, detail="only .html and .zip project packages are supported")
        content = await file.read()
        limit = int(os.getenv("WORK_ARTIFACT_MAX_BYTES", str(50 * 1024 * 1024)))
        if not content or len(content) > limit:
            raise HTTPException(status_code=422, detail="uploaded project is empty or exceeds the size limit")
        try:
            scan_upload(upload_scanner, content)
        except UnsafeUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        is_static_html = extension in {"html", "htm"}
        owner_user_id = session.user_id
        if ownerUserId.strip():
            owner = auth_service.user_for_id(ownerUserId.strip())
            if owner is None or owner.organization_id != session.organization_id or owner.role != "student":
                raise HTTPException(status_code=422, detail="target student must be an active student in the current organization")
            owner_user_id = owner.user_id
        work = catalog.create(
            project_id=f"upload-{owner_user_id}", organization_id=session.organization_id, owner_user_id=owner_user_id,
            kind="webpage", title=(title.strip() or filename)[:120], preview_url="", prompt="教师上传作品" if is_static_html else "教师上传网站工程包（含数据库项目需部署后配置预览地址）",
        )
        artifact = uploads.save(work.asset_id, session.organization_id, filename, file.content_type or ("text/html" if is_static_html else "application/zip"), content)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.uploaded", target_type="creative_asset", target_id=work.asset_id)
        deployment_record = None
        if not is_static_html:
            try:
                manifest = analyzer.analyze(content)
                env_template = {key: "" for key in (manifest.get("envTemplate") or {})}
                deployment_record = deployment_service.create(work.asset_id, session.organization_id, manifest, env_template)
                if audit_log:
                    audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.deployment_prepared", target_type="deployment", target_id=deployment_record.deployment_id)
            except (zipfile.BadZipFile, OSError, ValueError):
                deployment_record = None
        response = {**asset_payload(work), "artifact": artifact_payload(artifact), "uploadMode": "static_html" if is_static_html else "deployment_package"}
        if deployment_record:
            response["deployment"] = deployment_payload(deployment_record)
        else:
            response["deployment"] = None
        return response

    @router.get("/mine")
    def list_my_assets(session: SessionContext = Depends(require_role(session_dependency, "student"))) -> dict[str, object]:
        return {"works": [asset_payload(asset) for asset in catalog.list_for_owner(session.user_id, session.organization_id)]}

    @router.get("/review")
    def list_review_assets(
        kind: str | None = Query(default=None),
        review_state: str | None = Query(default=None, alias="reviewState"),
        featured: bool | None = Query(default=None),
        search: str | None = Query(default=None, max_length=80),
        session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin")),
    ) -> dict[str, object]:
        return {"works": [asset_payload(asset) for asset in catalog.list_for_review(session.organization_id, kind=kind, review_state=review_state, featured=featured, search=search)]}

    @router.get("/showcase")
    def list_showcase(kind: str | None = Query(default=None), limit: int = Query(default=24, ge=1, le=100), sort: str = Query(default="featured", pattern="^(featured|newest|popular)$"), session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        works = [asset for asset in catalog.list_showcase(session.organization_id, kind=kind, limit=100, sort=sort) if asset.visibility == "organization" or asset.owner_user_id == session.user_id]
        if sort == "popular":
            works.sort(key=lambda asset: interaction_store.like_count(asset.asset_id), reverse=True)
        return {"works": [asset_payload(asset) for asset in works[:limit]]}

    @router.post("/{asset_id}/review")
    def review_asset(asset_id: str, request: ReviewAssetRequest, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        try:
            asset = catalog.review(asset_id, session.organization_id, request.state, request.featured)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.reviewed", target_type="creative_asset", target_id=asset_id)
        return asset_payload(asset)

    @router.put("/{asset_id}/metadata")
    def update_asset_metadata(asset_id: str, request: UpdateAssetMetadataRequest, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        steps = None
        if request.processSteps is not None:
            steps = tuple(step.strip() for step in request.processSteps if step.strip())
            if len(steps) != len(request.processSteps):
                raise HTTPException(status_code=422, detail="process steps cannot be blank")
        try:
            current = catalog.get(asset_id, session.organization_id)
            grade_min = request.gradeMin if request.gradeMin is not None else current.grade_min
            grade_max = request.gradeMax if request.gradeMax is not None else current.grade_max
            if grade_min > grade_max:
                raise HTTPException(status_code=422, detail="minimum grade cannot exceed maximum grade")
            asset = catalog.update_metadata(
                asset_id,
                session.organization_id,
                title=request.title.strip() if request.title is not None else None,
                preview_url=request.previewUrl.strip() if request.previewUrl is not None else None,
                cover_url=request.coverUrl.strip() if request.coverUrl is not None else None,
                process_steps=steps,
                grade_min=grade_min,
                grade_max=grade_max,
                visibility=request.visibility,
                is_example=request.isExample,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.metadata_updated", target_type="creative_asset", target_id=asset_id)
        return asset_payload(asset)

    @router.post("/{asset_id}/media/{slot}")
    async def upload_showcase_media(asset_id: str, slot: str, file: UploadFile = File(...), session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        if slot not in {"cover", "preview"}:
            raise HTTPException(status_code=422, detail="media slot must be cover or preview")
        try:
            asset = catalog.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        filename = file.filename or "showcase-media"
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        image_extensions = {"jpg", "jpeg", "png", "webp", "gif"}
        media_extensions = image_extensions | {"mp3", "wav", "m4a", "mp4", "webm"}
        allowed_extensions = image_extensions if slot == "cover" else media_extensions
        if extension not in allowed_extensions:
            raise HTTPException(status_code=422, detail="unsupported showcase media file type")
        if slot == "preview" and asset.kind == "image" and extension not in image_extensions:
            raise HTTPException(status_code=422, detail="image works require an image preview")
        if slot == "preview" and asset.kind == "music" and extension not in {"mp3", "wav", "m4a"}:
            raise HTTPException(status_code=422, detail="music works require an audio preview")
        if slot == "preview" and asset.kind == "video" and extension not in {"mp4", "webm"}:
            raise HTTPException(status_code=422, detail="video works require a video preview")
        content = await file.read()
        limit = int(os.getenv("SHOWCASE_MEDIA_MAX_BYTES", str(50 * 1024 * 1024)))
        if not content or len(content) > limit:
            raise HTTPException(status_code=422, detail="showcase media is empty or exceeds the size limit")
        try:
            scan_upload(upload_scanner, content)
        except UnsafeUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        media = showcase_media_store.save(asset_id, session.organization_id, slot, filename, file.content_type or "application/octet-stream", content)
        media_url = f"/works/{asset_id}/media/{slot}"
        asset = catalog.update_metadata(asset_id, session.organization_id, cover_url=media_url if slot == "cover" else None, preview_url=media_url if slot == "preview" else None)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.media_uploaded", target_type="creative_asset", target_id=asset_id)
        return {"work": asset_payload(asset), "media": {"slot": media.slot, "filename": media.filename, "contentType": media.content_type, "size": media.size, "url": media_url}}

    @router.get("/{asset_id}/media/{slot}")
    def get_showcase_media(asset_id: str, slot: str, session: SessionContext = Depends(session_dependency)) -> Response:
        try:
            asset = catalog.get(asset_id, session.organization_id)
            if session.role == "student" and asset.owner_user_id != session.user_id and (asset.review_state != "approved" or asset.visibility == "private"):
                raise HTTPException(status_code=403, detail="work access denied")
            media = showcase_media_store.get(asset_id, session.organization_id, slot)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="showcase media not found") from exc
        return Response(showcase_media_store.read(media), media_type=media.content_type, headers={"Content-Disposition": f'inline; filename="{media.filename}"'})

    @router.delete("/{asset_id}")
    def delete_asset(asset_id: str, session: SessionContext = Depends(require_role(session_dependency, "organization_admin", "platform_admin"))) -> dict[str, str]:
        try:
            catalog.delete(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.deleted", target_type="creative_asset", target_id=asset_id)
        try:
            uploads.delete(asset_id, session.organization_id)
        except KeyError:
            pass
        return {"assetId": asset_id, "status": "deleted"}

    @router.get("/{asset_id}/download")
    def download_uploaded_work(asset_id: str, session: SessionContext = Depends(session_dependency)) -> Response:
        try:
            asset = catalog.get(asset_id, session.organization_id)
            artifact = uploads.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="uploaded work not found") from exc
        if session.role == "student" and asset.owner_user_id != session.user_id and (asset.review_state != "approved" or asset.visibility == "private"):
            raise HTTPException(status_code=403, detail="work access denied")
        return Response(uploads.read(artifact), media_type=artifact.content_type, headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'})

    @router.post("/review/batch")
    def batch_review(request: BatchReviewRequest, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        reviewed = []
        for asset_id in dict.fromkeys(request.assetIds):
            try:
                asset = catalog.review(asset_id, session.organization_id, request.state, request.featured)
                reviewed.append(asset_payload(asset))
            except KeyError:
                continue
        if audit_log:
            for asset in reviewed:
                audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.reviewed", target_type="creative_asset", target_id=asset["assetId"])
        return {"reviewed": len(reviewed), "works": reviewed}

    @router.post("/{asset_id}/like")
    def like_work(asset_id: str, request: LikeRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        try:
            catalog.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        liked = interaction_store.toggle_like(asset_id, session.user_id, request.enabled)
        return {"assetId": asset_id, "liked": liked, "likeCount": interaction_store.like_count(asset_id)}

    @router.get("/{asset_id}/comments")
    def list_comments(asset_id: str, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        return {"comments": [comment_payload(comment) for comment in interaction_store.list_comments(asset_id, session.organization_id)], "likeCount": interaction_store.like_count(asset_id), "liked": interaction_store.liked_by(asset_id, session.user_id)}

    @router.post("/{asset_id}/comments")
    def add_comment(asset_id: str, request: InteractionRequest, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        try:
            catalog.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if not request.body.strip():
            raise HTTPException(status_code=422, detail="comment body is required")
        comment = interaction_store.add_comment(asset_id, session.organization_id, session.user_id, session.role, request.body)
        return comment_payload(comment)

    @router.post("/{asset_id}/deployments/prepare")
    def prepare_deployment(asset_id: str, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        try:
            catalog.get(asset_id, session.organization_id)
            artifact = uploads.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="uploaded work not found") from exc
        if not artifact.content_type == "application/zip" and not artifact.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=422, detail="deployment preparation only supports .zip project packages")
        content = uploads.read(artifact)
        try:
            manifest = analyzer.analyze(content)
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="invalid zip project package") from exc
        env_template = {key: "" for key in (manifest.get("envTemplate") or {})}
        record = deployment_service.create(asset_id, session.organization_id, manifest, env_template)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.deployment_prepared", target_type="deployment", target_id=record.deployment_id)
        return deployment_payload(record)

    @router.get("/{asset_id}/deployments")
    def list_deployments(asset_id: str, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        try:
            catalog.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        return {"deployments": [deployment_payload(record) for record in deployment_service.list_for_asset(asset_id, session.organization_id)]}

    @router.get("/{asset_id}/deployments/{deployment_id}")
    def get_deployment(asset_id: str, deployment_id: str, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        try:
            record = deployment_service.get(deployment_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="deployment not found") from exc
        if record.asset_id != asset_id:
            raise HTTPException(status_code=404, detail="deployment not found")
        return deployment_payload(record)

    @router.put("/{asset_id}/deployments/{deployment_id}/publish")
    def publish_deployment(asset_id: str, deployment_id: str, request: PublishDeploymentRequest, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        parsed = urlparse(request.previewUrl.strip())
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise HTTPException(status_code=422, detail="published preview URL must be a valid HTTPS URL")
        try:
            catalog.get(asset_id, session.organization_id)
            record = deployment_service.get(deployment_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="deployment not found") from exc
        if record.asset_id != asset_id:
            raise HTTPException(status_code=404, detail="deployment not found")
        published = deployment_service.publish(deployment_id, session.organization_id, request.previewUrl.strip())
        asset = catalog.update_metadata(asset_id, session.organization_id, preview_url=published.published_url)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="work.deployment_published", target_type="deployment", target_id=deployment_id)
        return {"deployment": deployment_payload(published), "work": asset_payload(asset)}

    @router.get("/{asset_id}")
    def get_asset(asset_id: str, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        try:
            asset = catalog.get(asset_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if session.role == "student" and asset.owner_user_id != session.user_id and (asset.review_state != "approved" or asset.visibility == "private"):
            raise HTTPException(status_code=403, detail="work access denied")
        return asset_payload(asset)

    return router


def asset_payload(asset: CreativeAsset) -> dict[str, object]:
    return {
        "assetId": asset.asset_id, "projectId": asset.project_id, "ownerUserId": asset.owner_user_id,
        "kind": asset.kind, "title": asset.title, "previewUrl": asset.preview_url, "prompt": asset.prompt,
        "reviewState": asset.review_state, "featured": asset.featured, "coverUrl": asset.cover_url,
        "processSteps": list(asset.process_steps), "gradeMin": asset.grade_min, "gradeMax": asset.grade_max,
        "visibility": asset.visibility, "isExample": asset.is_example,
    }


def artifact_payload(artifact) -> dict[str, object]:
    return {"filename": artifact.filename, "contentType": artifact.content_type, "size": artifact.size}


def comment_payload(comment) -> dict[str, object]:
    return {"commentId": comment.comment_id, "authorUserId": comment.author_user_id, "authorRole": comment.author_role, "body": comment.body, "createdAt": comment.created_at}
