from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.reports.service import LearningEvent, ReportService
from .catalog import CourseCatalog
from .learning import LearningStore, progress_payload, submission_payload


class ProgressRequest(BaseModel):
    percent: int = Field(ge=0, le=100)
    completed: bool = False
    lastBlockIndex: int = Field(ge=0)


class SubmissionRequest(BaseModel):
    content: str = Field(min_length=1, max_length=6000)


class AnnotationRequest(BaseModel):
    feedback: str = Field(default="", max_length=4000)
    status: str = Field(default="reviewed", pattern="^(reviewed|rejected)$")


def create_learning_router(auth_service: AuthService, courses: CourseCatalog, learning: LearningStore, audit_log: AuditLog | None = None, reports: ReportService | None = None, classrooms: AssistanceManager | None = None) -> APIRouter:
    router = APIRouter(prefix="/learning", tags=["learning"])
    session_dependency = require_session(auth_service)
    student_dependency = require_role(session_dependency, "student")
    teacher_dependency = require_role(session_dependency, "teacher", "organization_admin", "platform_admin")
    access = TeachingAccess(auth_service, classrooms)

    def published_course_for_student(student_id: str, organization_id: str, course_id: str):
        user = auth_service.user_for_id(student_id)
        if user is None or user.organization_id != organization_id or not user.class_id:
            raise HTTPException(status_code=404, detail="classroom not found")
        published = {course.course_id: course for course in courses.list_for_class(user.class_id, organization_id)}
        if course_id not in published:
            raise HTTPException(status_code=404, detail="course not published to your class")
        return published[course_id]

    @router.put("/progress/{course_id}")
    def upsert_progress(course_id: str, request: ProgressRequest, session: SessionContext = Depends(student_dependency)) -> dict[str, object]:
        course = published_course_for_student(session.user_id, session.organization_id, course_id)
        was_completed = False
        try:
            was_completed = learning.get_progress(session.user_id, course_id, session.organization_id).completed
        except KeyError:
            pass
        record = learning.upsert_progress(session.user_id, course_id, session.organization_id, request.percent, request.completed, request.lastBlockIndex)
        if reports and request.completed and not was_completed:
            reports.record(LearningEvent(session.user_id, "lesson.completed", course.title))
        return progress_payload(record)

    @router.get("/me/progress")
    def my_progress(session: SessionContext = Depends(student_dependency)) -> dict[str, list[dict[str, object]]]:
        return {"progress": [progress_payload(record) for record in learning.list_progress_for_student(session.user_id, session.organization_id)]}

    @router.post("/courses/{course_id}/submissions")
    def submit_homework(course_id: str, request: SubmissionRequest, session: SessionContext = Depends(student_dependency)) -> dict[str, object]:
        course = published_course_for_student(session.user_id, session.organization_id, course_id)
        submission = learning.submit_homework(session.user_id, course_id, session.organization_id, request.content)
        if reports:
            reports.record(LearningEvent(session.user_id, "homework.submitted", course.title))
        return submission_payload(submission)

    @router.get("/me/submissions")
    def my_submissions(session: SessionContext = Depends(student_dependency)) -> dict[str, list[dict[str, object]]]:
        return {"submissions": [submission_payload(submission) for submission in learning.list_submissions_for_student(session.user_id, session.organization_id)]}

    @router.get("/courses/{course_id}/progress")
    def course_progress(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        try:
            courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        return {"progress": [progress_payload(record) for record in learning.list_progress_for_course(course_id, session.organization_id) if access.can_manage_student(session, record.student_id)]}

    @router.get("/courses/{course_id}/submissions")
    def course_submissions(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        try:
            courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        return {"submissions": [submission_payload(submission) for submission in learning.list_submissions_for_course(course_id, session.organization_id) if access.can_manage_student(session, submission.student_id)]}

    @router.post("/submissions/{submission_id}/annotate")
    def annotate_submission(submission_id: str, request: AnnotationRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            current = learning.get_submission(submission_id, session.organization_id)
            access.require_student(session, current.student_id)
            submission = learning.annotate(submission_id, session.organization_id, request.feedback, request.status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="homework submission not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="homework.annotated", target_type="homework_submission", target_id=submission_id)
        if reports:
            reports.record(LearningEvent(submission.student_id, "homework.reviewed", submission.course_id))
        return submission_payload(submission)

    return router
