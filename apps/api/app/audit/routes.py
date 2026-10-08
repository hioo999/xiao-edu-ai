import csv
from io import StringIO

from fastapi import APIRouter, Depends, Response, Query

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from .service import AuditLog


def create_audit_router(auth_service: AuthService, audit_log: AuditLog) -> APIRouter:
    router = APIRouter(prefix="/audit", tags=["audit"])
    admin_dependency = require_role(require_session(auth_service), "platform_admin", "organization_admin")

    @router.get("")
    def list_audit_logs(limit: int = Query(default=100, ge=1, le=200), offset: int = Query(default=0, ge=0), actor_id: str | None = Query(default=None, alias="actorId"), action: str | None = None, target_type: str | None = Query(default=None, alias="targetType"), since: str | None = None, until: str | None = None, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        safe_limit = max(1, min(limit, 200))
        return {"records": [record.__dict__ for record in audit_log.list_for_organization(session.organization_id, limit=safe_limit, offset=offset, actor_id=actor_id, action=action, target_type=target_type, since=since, until=until)], "offset": offset, "limit": safe_limit}

    @router.get("/export.csv")
    def export_audit_logs(session: SessionContext = Depends(admin_dependency)) -> Response:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["record_id", "organization_id", "actor_id", "action", "target_type", "target_id", "created_at"])
        for record in audit_log.list_for_organization(session.organization_id, limit=200):
            writer.writerow([record.record_id, record.organization_id, record.actor_id, record.action, record.target_type, record.target_id, record.created_at])
        return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit-records.csv"'})

    return router
