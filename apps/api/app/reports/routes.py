from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from .service import LearningEvent, ReportService


class LearningEventRequest(BaseModel):
    eventType: str = Field(min_length=3, max_length=80)
    label: str = Field(min_length=1, max_length=300)


def create_report_router(auth_service: AuthService, reports: ReportService) -> APIRouter:
    router = APIRouter(prefix="/reports", tags=["reports"])
    session_dependency = require_session(auth_service)

    @router.post("/events")
    def record_event(request: LearningEventRequest, session: SessionContext = Depends(require_role(session_dependency, "student"))) -> dict[str, str]:
        reports.record(LearningEvent(session.user_id, request.eventType, request.label))
        return {"status": "recorded"}

    @router.get("/me")
    def my_report(session: SessionContext = Depends(require_role(session_dependency, "student"))) -> dict[str, object]:
        try:
            return reports.for_student(session.user_id)
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail="student report is not available") from exc

    @router.get("/students/{student_id}")
    def student_report(student_id: str, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        try:
            return reports.for_student(student_id)
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail="student report is not available") from exc

    return router
