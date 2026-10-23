from datetime import datetime, timezone
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .dependencies import require_role, require_session
from .provisioning_routes import AccountExpiryRequest, AccountStateRequest
from .staff_lifecycle import normalize_account_expiry


class StaffPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=256)


class StaffHandoverRequest(BaseModel):
    replacementUserId: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=500)


def create_staff_router(auth, lifecycle, audit=None):
    router = APIRouter(prefix="/organizations/{organization_id}/staff", tags=["staff-lifecycle"])
    administrator = require_role(require_session(auth), "platform_admin", "organization_admin")

    def permitted(organization_id, username, session):
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        return lifecycle.staff(organization_id, username)

    def record(organization_id, user_id, session, action):
        if audit:
            audit.record(organization_id=organization_id, actor_id=session.user_id, action=action, target_type="staff", target_id=user_id)

    @router.post("/{username}/reset-password")
    def reset_password(organization_id: str, username: str, request: StaffPasswordRequest, session=Depends(administrator)):
        with lifecycle.lock:
            user = permitted(organization_id, username, session)
            lifecycle.validate_change(organization_id, username, session)
            try:
                auth.reset_password(username, organization_id, request.password)
            except sqlite3.Error as exc:
                raise HTTPException(status_code=503, detail="password reset failed; credentials were not changed") from exc
            lifecycle.revoke_assistance(user.user_id)
            record(organization_id, user.user_id, session, "staff.password_reset")
        return {"username": username, "status": "password_reset"}

    @router.put("/{username}/state")
    def set_state(organization_id: str, username: str, request: AccountStateRequest, session=Depends(administrator)):
        with lifecycle.lock:
            user = permitted(organization_id, username, session)
            lifecycle.validate_change(organization_id, username, session, deactivating=not request.enabled)
            try:
                auth.set_enabled(username, organization_id, request.enabled)
            except sqlite3.Error as exc:
                raise HTTPException(status_code=503, detail="account state could not be updated") from exc
            if not request.enabled:
                lifecycle.revoke_assistance(user.user_id)
            record(organization_id, user.user_id, session, "staff.state_changed")
        return {"username": username, "enabled": request.enabled}

    @router.put("/{username}/expiry")
    def set_expiry(organization_id: str, username: str, request: AccountExpiryRequest, session=Depends(administrator)):
        expires_at = normalize_account_expiry(request.expiresAt)
        with lifecycle.lock:
            user = permitted(organization_id, username, session)
            deactivating = expires_at is not None and expires_at <= datetime.now(timezone.utc)
            lifecycle.validate_change(organization_id, username, session, deactivating=deactivating)
            try:
                auth.set_expiry(username, organization_id, expires_at)
            except sqlite3.Error as exc:
                raise HTTPException(status_code=503, detail="account expiry could not be updated") from exc
            if deactivating:
                lifecycle.revoke_assistance(user.user_id)
            record(organization_id, user.user_id, session, "staff.expiry_changed")
        return {"username": username, "expiresAt": expires_at.isoformat() if expires_at else None}

    @router.post("/{username}/revoke-sessions")
    def revoke_sessions(organization_id: str, username: str, session=Depends(administrator)):
        with lifecycle.lock:
            user = permitted(organization_id, username, session)
            lifecycle.validate_change(organization_id, username, session)
            auth.revoke_user_sessions(user.user_id)
            lifecycle.revoke_assistance(user.user_id)
            record(organization_id, user.user_id, session, "staff.sessions_revoked")
        return {"username": username, "status": "sessions_revoked"}

    @router.get("/{username}/handover-plan")
    def handover_plan(organization_id: str, username: str, session=Depends(administrator)):
        permitted(organization_id, username, session)
        return lifecycle.plan(organization_id, username)

    @router.post("/{username}/handover")
    def handover(organization_id: str, username: str, request: StaffHandoverRequest, session=Depends(administrator)):
        permitted(organization_id, username, session)
        if not request.reason.strip():
            raise HTTPException(status_code=422, detail="handover reason is required")
        return lifecycle.handover(organization_id, username, request.replacementUserId, session, request.reason.strip())

    @router.get("/{username}/handover-history")
    def history(organization_id: str, username: str, session=Depends(administrator)):
        permitted(organization_id, username, session)
        return {"handovers": lifecycle.history(organization_id, username)}

    return router
