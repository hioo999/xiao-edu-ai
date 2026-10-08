from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from .service import AuthService, SessionContext
from .dependencies import require_session


class LoginRequest(BaseModel):
    username: str
    password: str


class BootstrapAdminRequest(BaseModel):
    username: str
    password: str
    organizationId: str = "org-001"


def create_auth_router(service: AuthService) -> APIRouter:
    router = APIRouter()

    @router.post("/login")
    def login(request: LoginRequest) -> dict[str, str]:
        try:
            session = service.login(request.username, request.password)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail="invalid credentials") from exc

        access_token, expires_at = service.create_access_session(session)
        return {
            "userId": session.user_id,
            "organizationId": session.organization_id,
            "role": session.role,
            "accessToken": access_token,
            "expiresAt": expires_at.isoformat(),
        }

    @router.post("/logout")
    def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="authentication required")
        service.revoke_access_session(authorization.removeprefix("Bearer ").strip())
        return {"status": "logged_out"}

    @router.get("/me")
    def current_user(session: SessionContext = Depends(require_session(service))) -> dict[str, str | None]:
        user = service.user_for_id(session.user_id)
        return {"userId": session.user_id, "organizationId": session.organization_id, "role": session.role, "classId": user.class_id if user else None}

    @router.post("/bootstrap-admin")
    def bootstrap_admin(request: BootstrapAdminRequest) -> dict[str, str]:
        if len(request.username.strip()) < 3 or len(request.password) < 8 or not request.organizationId.strip():
            raise HTTPException(status_code=422, detail="username, password and organization are required")
        try:
            session = service.bootstrap_platform_admin(request.username.strip(), request.password, request.organizationId.strip())
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail="platform administrator already exists") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="username already exists") from exc
        access_token, expires_at = service.create_access_session(session)
        return {"userId": session.user_id, "organizationId": session.organization_id, "role": session.role, "accessToken": access_token, "expiresAt": expires_at.isoformat()}

    return router
