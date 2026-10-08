from collections.abc import Callable

from fastapi import Depends, Header, HTTPException

from .service import AuthService, SessionContext


def require_session(auth_service: AuthService):
    def dependency(authorization: str | None = Header(default=None)) -> SessionContext:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="authentication required")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            return auth_service.resolve_access_session(token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail="authentication required") from exc

    return dependency


def require_role(session_dependency, *roles: str) -> Callable[[SessionContext], SessionContext]:
    def dependency(session: SessionContext = Depends(session_dependency)) -> SessionContext:
        if session.role not in roles:
            raise HTTPException(status_code=403, detail="role access denied")
        return session

    return dependency
