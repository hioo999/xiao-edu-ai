from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from .service import UsageLedger


class QuotaLimitRequest(BaseModel):
    metric: str = Field(pattern="^(text|image|video|music|storage)$")
    limit: int = Field(ge=0)
    scope: str = Field(default="organization", pattern="^(platform|organization|class|student)$")
    scopeId: str | None = None


def create_usage_router(auth_service: AuthService, ledger: UsageLedger, audit_log: AuditLog | None = None) -> APIRouter:
    router = APIRouter(prefix="/usage", tags=["usage"])
    session_dependency = require_session(auth_service)
    admin_dependency = require_role(session_dependency, "platform_admin", "organization_admin")

    @router.get("/summary")
    def summary(scope: str = "organization", scope_id: str | None = None, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        if scope not in {"platform", "organization", "class", "student"}:
            raise HTTPException(status_code=422, detail="unsupported quota scope")
        effective_scope_id = scope_id or session.organization_id
        if session.role != "platform_admin" and (scope != "organization" or effective_scope_id != session.organization_id):
            raise HTTPException(status_code=403, detail="organization access denied")
        return {"scope": scope, "scopeId": effective_scope_id, "metrics": ledger.summary(scope, effective_scope_id)}

    @router.get("/mine")
    def my_summary(session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        """Expose only the effective creation allowance to the signed-in learner."""
        user = auth_service.user_for_id(session.user_id)
        scopes = [("student", session.user_id)]
        if user and user.class_id:
            scopes.append(("class", user.class_id))
        scopes.append(("organization", session.organization_id))
        metrics = []
        for metric in ("text", "image", "music", "video"):
            selected = ledger.configured_scope(scopes, metric)
            if selected is None:
                continue
            record = next((item for item in ledger.summary(*selected) if item["metric"] == metric), None)
            if record:
                metrics.append({**record, "scope": selected[0], "scopeId": selected[1], "remaining": max(0, int(record["limit"]) - int(record["used"]) - int(record["reserved"]))})
        return {"metrics": metrics}

    @router.post("/limits")
    def set_limit(request: QuotaLimitRequest, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        scope_id = request.scopeId or session.organization_id
        if session.role != "platform_admin" and (request.scope != "organization" or scope_id != session.organization_id):
            raise HTTPException(status_code=403, detail="organization access denied")
        ledger.set_limit(request.scope, scope_id, request.metric, request.limit)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="quota.limit_changed", target_type="quota", target_id=f"{request.scope}:{scope_id}:{request.metric}")
        return {"scope": request.scope, "scopeId": scope_id, "metric": request.metric, "limit": request.limit}

    return router
