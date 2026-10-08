from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .dependencies import require_role, require_session
from .service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog


class BatchProvisionRequest(BaseModel):
    prefix: str
    count: int
    classId: str
    initialPassword: str
    expiresAt: datetime | None = None


class ResetPasswordRequest(BaseModel):
    password: str


class AccountStateRequest(BaseModel):
    enabled: bool


class AccountExpiryRequest(BaseModel):
    expiresAt: datetime | None = None


class StaffAccountRequest(BaseModel):
    username: str
    password: str
    role: str
    expiresAt: datetime | None = None


class BulkAccountStateRequest(BaseModel):
    usernames: list[str]
    enabled: bool


class BulkAccountExpiryRequest(BaseModel):
    usernames: list[str]
    expiresAt: datetime | None = None


def create_provisioning_router(auth_service: AuthService, audit_log: AuditLog | None = None) -> APIRouter:
    router = APIRouter(prefix="/organizations", tags=["students"])
    session_dependency = require_session(auth_service)
    staff_dependency = require_role(
        session_dependency,
        "platform_admin",
        "organization_admin",
        "teacher",
    )
    account_admin_dependency = require_role(session_dependency, "platform_admin", "organization_admin")

    @router.get("/{organization_id}/staff")
    def list_staff(organization_id: str, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, object]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        return {
            "staff": [
                {
                    "username": username,
                    "userId": user.user_id,
                    "organizationId": user.organization_id,
                    "role": user.role,
                    "enabled": user.enabled,
                    "expiresAt": user.expires_at.isoformat() if user.expires_at else None,
                }
                for username, user in auth_service.users_for_organization(organization_id)
                if user.role in {"teacher", "organization_admin"}
            ]
        }

    @router.post("/{organization_id}/staff")
    def create_staff(organization_id: str, request: StaffAccountRequest, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, object]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        if request.role not in {"teacher", "organization_admin"}:
            raise HTTPException(status_code=422, detail="unsupported staff role")
        expires_at = request.expiresAt
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        try:
            user = auth_service.create_staff_user(username=request.username, password=request.password, organization_id=organization_id, role=request.role, expires_at=expires_at)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="staff.created", target_type="staff", target_id=request.username)
        return {"username": request.username.strip(), "userId": user.user_id, "role": user.role, "expiresAt": user.expires_at.isoformat() if user.expires_at else None}

    @router.post("/{organization_id}/accounts/bulk-state")
    def bulk_account_state(organization_id: str, request: BulkAccountStateRequest, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, int]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        changed = auth_service.set_enabled_bulk(request.usernames, organization_id, request.enabled)
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="accounts.bulk_state_changed", target_type="organization", target_id=organization_id)
        return {"changed": changed}

    @router.post("/{organization_id}/accounts/bulk-expiry")
    def bulk_account_expiry(organization_id: str, request: BulkAccountExpiryRequest, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, int]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        expires_at = request.expiresAt
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        changed = auth_service.set_expiry_bulk(request.usernames, organization_id, expires_at)
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="accounts.bulk_expiry_changed", target_type="organization", target_id=organization_id)
        return {"changed": changed}

    @router.post("/{organization_id}/students/batch")
    def batch_provision(
        organization_id: str,
        request: BatchProvisionRequest,
        session: SessionContext = Depends(staff_dependency),
    ) -> dict[str, list[dict[str, str]]]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        expires_at = request.expiresAt
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        students = auth_service.provision_students(
            prefix=request.prefix,
            count=request.count,
            class_id=request.classId,
            initial_password=request.initialPassword,
            organization_id=organization_id,
            expires_at=expires_at,
        )
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="students.provisioned", target_type="classroom", target_id=request.classId)
        return {
            "students": [
                {
                    "username": student.username,
                    "classId": student.class_id,
                    "initialPassword": student.initial_password,
                }
                for student in students
            ]
        }

    @router.get("/{organization_id}/students")
    def list_students(
        organization_id: str,
        search: str | None = Query(default=None, max_length=80),
        class_id: str | None = Query(default=None, alias="classId", max_length=80),
        enabled: bool | None = Query(default=None),
        expired: bool | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        session: SessionContext = Depends(staff_dependency),
    ) -> dict[str, object]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        students = auth_service.users_for_organization(
            organization_id,
            role="student",
            search=search,
            class_id=class_id,
            enabled=enabled,
            expired=expired,
            offset=offset,
            limit=limit,
        )
        return {
            "students": [
                {
                    "username": username,
                    "userId": student.user_id,
                    "organizationId": student.organization_id,
                    "classId": student.class_id,
                    "enabled": student.enabled,
                    "expired": student.expires_at is not None and student.expires_at <= datetime.now(timezone.utc),
                    "expiresAt": student.expires_at.isoformat() if student.expires_at else None,
                }
                for username, student in students
            ],
            "offset": offset,
            "limit": limit,
        }

    @router.post("/{organization_id}/students/{username}/reset-password")
    def reset_student_password(organization_id: str, username: str, request: ResetPasswordRequest, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, str]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        if len(request.password) < 8:
            raise HTTPException(status_code=422, detail="password must be at least 8 characters")
        try:
            auth_service.reset_password(username, organization_id, request.password)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="student not found") from exc
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="student.password_reset", target_type="student", target_id=username)
        return {"username": username, "status": "password_reset"}

    @router.post("/{organization_id}/students/{username}/state")
    def set_student_state(organization_id: str, username: str, request: AccountStateRequest, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, object]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        try:
            auth_service.set_enabled(username, organization_id, request.enabled)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="student not found") from exc
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="student.enabled_changed", target_type="student", target_id=username)
        return {"username": username, "enabled": request.enabled}

    @router.post("/{organization_id}/students/{username}/expiry")
    def set_student_expiry(organization_id: str, username: str, request: AccountExpiryRequest, session: SessionContext = Depends(account_admin_dependency)) -> dict[str, object]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="organization access denied")
        expires_at = request.expiresAt
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        try:
            auth_service.set_expiry(username, organization_id, expires_at)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="student not found") from exc
        if audit_log:
            audit_log.record(organization_id=organization_id, actor_id=session.user_id, action="student.expiry_changed", target_type="student", target_id=username)
        return {"username": username, "expiresAt": expires_at.isoformat() if expires_at else None}

    return router
