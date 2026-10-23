from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Literal

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog

from .service import OrganizationSettings, SettingsStore


class SettingsPayload(BaseModel):
    displayName: str = Field(min_length=1, max_length=80)
    studentHomeEnabled: bool = True
    maintenanceMessage: str = Field(default="", max_length=240)
    showcaseColumns: int = Field(default=4, ge=3, le=6)
    showcaseRows: int = Field(default=2, ge=1, le=3)
    showcaseSort: str = Field(default="featured", pattern="^(featured|newest|popular)$")
    showcaseKind: str = Field(default="all", pattern="^(all|webpage|image|music|video)$")
    videoDurationSeconds: Literal[5, 10] | None = None


def payload(settings: OrganizationSettings) -> dict[str, object]:
    return {"displayName": settings.display_name, "studentHomeEnabled": settings.student_home_enabled, "maintenanceMessage": settings.maintenance_message, "showcaseColumns": settings.showcase_columns, "showcaseRows": settings.showcase_rows, "showcaseSort": settings.showcase_sort, "showcaseKind": settings.showcase_kind, "videoDurationSeconds": settings.video_duration_seconds}


def create_settings_router(auth_service: AuthService, store: SettingsStore, audit_log: AuditLog | None = None) -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])
    admin_dependency = require_role(require_session(auth_service), "platform_admin", "organization_admin")

    @router.get("")
    def get_settings(session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return payload(store.get(session.organization_id))

    @router.put("")
    def save_settings(request: SettingsPayload, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        video_duration_seconds = request.videoDurationSeconds
        if video_duration_seconds is None:
            video_duration_seconds = store.get(session.organization_id).video_duration_seconds
        saved = store.save(OrganizationSettings(session.organization_id, request.displayName.strip(), request.studentHomeEnabled, request.maintenanceMessage.strip(), request.showcaseColumns, request.showcaseRows, request.showcaseSort, request.showcaseKind, video_duration_seconds))
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="settings.saved", target_type="organization_settings", target_id=session.organization_id)
        return payload(saved)

    @router.post("/security/revoke-sessions")
    def revoke_sessions(session: SessionContext = Depends(admin_dependency)) -> dict[str, int]:
        revoked = auth_service.revoke_organization_sessions(session.organization_id, except_user_id=session.user_id)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="security.sessions_revoked", target_type="organization", target_id=session.organization_id)
        return {"revoked": revoked}

    @router.get("/student-access")
    def student_access(session: SessionContext = Depends(require_session(auth_service))) -> dict[str, object]:
        settings = store.get(session.organization_id)
        return {
            "enabled": session.role != "student" or settings.student_home_enabled,
            "displayName": settings.display_name,
            "maintenanceMessage": settings.maintenance_message,
            "showcaseColumns": settings.showcase_columns,
            "showcaseRows": settings.showcase_rows,
            "showcaseSort": settings.showcase_sort,
            "showcaseKind": settings.showcase_kind,
            "videoDurationSeconds": settings.video_duration_seconds,
        }

    return router
