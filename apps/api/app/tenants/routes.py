from fastapi import APIRouter, Depends

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext


def create_tenant_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/organizations", tags=["organizations"])
    session_dependency = require_session(auth_service)

    @router.get("/{organization_id}")
    def get_organization(
        organization_id: str,
        session: SessionContext = Depends(
            require_role(
                session_dependency,
                "platform_admin",
                "organization_admin",
            )
        ),
    ) -> dict[str, str]:
        if session.role != "platform_admin" and session.organization_id != organization_id:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="organization access denied")
        return {"organizationId": organization_id, "access": "granted"}

    return router
