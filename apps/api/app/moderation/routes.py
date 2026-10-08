from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from .service import ModerationDecision, ModerationService


class ModerationRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    mode: str = Field(default="classroom", pattern="^(classroom|free_creation)$")


class ModerationPolicyPayload(BaseModel):
    enabled: bool = True
    blockedTerms: list[str] = Field(default_factory=list)


def _policy_payload(service: ModerationService) -> dict[str, object]:
    policy = service.policy()
    return {"enabled": policy.enabled, "modes": list(policy.modes), "status": "active" if policy.enabled else "paused", "blockedTerms": list(policy.blocked_terms)}


def create_moderation_router(auth_service: AuthService, moderation: ModerationService) -> APIRouter:
    router = APIRouter(prefix="/moderation", tags=["moderation"])
    session_dependency = require_session(auth_service)
    admin_dependency = require_role(session_dependency, "platform_admin", "organization_admin")

    @router.post("/check")
    def check_content(request: ModerationRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, str]:
        decision = moderation.check(request.content, mode=request.mode)
        if decision is ModerationDecision.BLOCKED:
            raise HTTPException(status_code=422, detail="content is blocked by safety policy")
        return {"decision": decision, "mode": request.mode}

    @router.get("/policy")
    def get_policy(session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return _policy_payload(moderation)

    @router.put("/policy")
    def update_policy(request: ModerationPolicyPayload, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        moderation.update_policy(enabled=request.enabled, blocked_terms=request.blockedTerms)
        return _policy_payload(moderation)

    return router
