from datetime import datetime, timedelta, timezone
import os

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_session
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.projects.asset_routes import asset_payload
from apps.api.app.projects.showcase_media import ShowcaseMediaStore
from apps.api.app.projects.artifact_storage import WorkArtifactStore
from .links import ShareLinkService
from apps.api.app.media.files import GeneratedFileAccess


class CreateShareRequest(BaseModel):
    assetId: str
    expiresInHours: int = Field(default=72, ge=1, le=24 * 30)
    allowDownload: bool = False


def create_share_router(auth_service: AuthService, links: ShareLinkService, assets: CreativeAssetCatalog, media_store: ShowcaseMediaStore | None = None, artifact_store: WorkArtifactStore | None = None, classrooms: AssistanceManager | None = None, generated_files: GeneratedFileAccess | None = None) -> APIRouter:
    router = APIRouter(prefix="/shares", tags=["shares"])
    session_dependency = require_session(auth_service)
    showcase_media = media_store or ShowcaseMediaStore(os.getenv("SHOWCASE_MEDIA_STORAGE_PATH", "var/showcase-media"))
    access = TeachingAccess(auth_service, classrooms)

    @router.post("")
    def create_share(request: CreateShareRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        try:
            asset = assets.get(request.assetId, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if asset.owner_user_id != session.user_id and session.role not in {"teacher", "organization_admin", "platform_admin"}:
            raise HTTPException(status_code=403, detail="work access denied")
        if session.role == "teacher" and asset.owner_user_id != session.user_id:
            access.require_student(session, asset.owner_user_id)
        if asset.review_state != "approved":
            raise HTTPException(status_code=409, detail="work must be approved before sharing")
        link = links.create(asset.asset_id, expires_at=datetime.now(timezone.utc) + timedelta(hours=request.expiresInHours), allow_download=request.allowDownload, organization_id=session.organization_id, owner_user_id=session.user_id)
        return {"token": link.token, "expiresAt": link.expires_at.isoformat(), "allowDownload": link.allow_download}

    @router.post("/{token}/revoke")
    def revoke_share(token: str, session: SessionContext = Depends(session_dependency)) -> dict[str, str]:
        try:
            link = links.get(token)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="share link not found") from exc
        if link.organization_id != session.organization_id:
            raise HTTPException(status_code=404, detail="share link not found")
        if link.owner_user_id != session.user_id and session.role not in {"teacher", "organization_admin", "platform_admin"}:
            raise HTTPException(status_code=403, detail="share access denied")
        if session.role == "teacher" and link.owner_user_id != session.user_id:
            try:
                asset = assets.get(link.project_id, session.organization_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="work not found") from exc
            access.require_student(session, asset.owner_user_id)
        links.revoke(token)
        return {"token": token, "status": "revoked"}

    @router.get("/public/{token}")
    def public_share(token: str) -> dict[str, object]:
        if not links.is_accessible(token):
            raise HTTPException(status_code=404, detail="share link is unavailable")
        link = links.get(token)
        try:
            asset = assets.get(link.project_id, link.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if asset.review_state != "approved":
            raise HTTPException(status_code=404, detail="share link is unavailable")
        work = asset_payload(asset)
        if generated_files:
            for field, slot in (("previewUrl", "preview"), ("coverUrl", "cover")):
                if generated_files.is_generated_url(str(work[field])):
                    work[field] = f"/shares/public/{token}/media/{slot}"
        if asset.kind == "webpage" and artifact_store is not None:
            try:
                artifact = artifact_store.get(asset.asset_id, link.organization_id)
                if artifact.content_type == "text/html":
                    work["content"] = artifact_store.read(artifact).decode("utf-8")
            except (KeyError, FileNotFoundError, UnicodeDecodeError):
                pass
        return {"work": work, "allowDownload": link.allow_download}

    @router.get("/public/{token}/media/{slot}")
    def public_share_media(token: str, slot: str) -> Response:
        if slot not in {"cover", "preview"} or not links.is_accessible(token):
            raise HTTPException(status_code=404, detail="share media not found")
        link = links.get(token)
        asset = None
        try:
            asset = assets.get(link.project_id, link.organization_id)
            if asset.review_state != "approved":
                raise KeyError(link.project_id)
            media = showcase_media.get(asset.asset_id, link.organization_id, slot)
            content = showcase_media.read(media)
        except (KeyError, FileNotFoundError) as exc:
            if generated_files and asset is not None and asset.review_state == "approved":
                try:
                    url = asset.preview_url if slot == "preview" else asset.cover_url
                    return generated_files.response(generated_files.asset_file(asset, url), public=True)
                except (KeyError, OSError, ValueError):
                    pass
            raise HTTPException(status_code=404, detail="share media not found") from exc
        return Response(content, media_type=media.content_type, headers={"Cache-Control": "no-store"})

    return router
