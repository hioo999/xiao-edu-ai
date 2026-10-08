from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.projects.asset_routes import asset_payload
from .links import ShareLinkService


class CreateShareRequest(BaseModel):
    assetId: str
    expiresInHours: int = Field(default=72, ge=1, le=24 * 30)
    allowDownload: bool = False


def create_share_router(auth_service: AuthService, links: ShareLinkService, assets: CreativeAssetCatalog) -> APIRouter:
    router = APIRouter(prefix="/shares", tags=["shares"])
    session_dependency = require_session(auth_service)

    @router.post("")
    def create_share(request: CreateShareRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        try:
            asset = assets.get(request.assetId, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="work not found") from exc
        if asset.owner_user_id != session.user_id and session.role not in {"teacher", "organization_admin", "platform_admin"}:
            raise HTTPException(status_code=403, detail="work access denied")
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
        return {"work": asset_payload(asset), "allowDownload": link.allow_download}

    return router
