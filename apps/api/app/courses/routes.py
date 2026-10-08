from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.core.scanning import UnsafeUploadError, build_upload_scanner, scan_upload
from .catalog import CourseCatalog, CourseRecord
from .exporter import Course, LessonBlock, export_offline_html
from .file_validation import validate_course_material
from .storage import CourseMaterialStore


class CourseBlockRequest(BaseModel):
    kind: str
    content: str
    authoredBy: str = "teacher"


class CourseRequest(BaseModel):
    courseId: str
    title: str
    summary: str = ""
    blocks: list[CourseBlockRequest] = []
    teacherScript: str = ""
    promptExamples: list[str] = []
    studentFlow: list[str] = []
    published: bool = False

class PublishCourseRequest(BaseModel):
    classId: str


def create_course_router(auth_service: AuthService, material_store: CourseMaterialStore, catalog: CourseCatalog | None = None, audit_log: AuditLog | None = None) -> APIRouter:
    router = APIRouter(prefix="/courses", tags=["courses"])
    teacher_dependency = require_role(require_session(auth_service), "teacher", "organization_admin", "platform_admin")
    courses = catalog or CourseCatalog()
    upload_scanner = build_upload_scanner()

    @router.get("")
    def list_courses(session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        return {"courses": [course_payload(course) for course in courses.list_for_organization(session.organization_id)]}

    @router.get("/{course_id}")
    def get_course(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            return course_payload(courses.get(course_id, session.organization_id))
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc

    @router.post("")
    def save_course(request: CourseRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        allowed_kinds = {"text", "image", "video", "code", "attachment", "interaction", "step", "challenge"}
        if any(block.kind not in allowed_kinds or block.authoredBy not in {"teacher", "ai"} for block in request.blocks):
            raise HTTPException(status_code=422, detail="unsupported course block")
        if not request.title.strip():
            raise HTTPException(status_code=422, detail="course title is required")
        course = CourseRecord(request.courseId, session.organization_id, session.user_id, request.title.strip(), request.summary.strip(), tuple(LessonBlock(kind=block.kind, content=block.content, authored_by=block.authoredBy) for block in request.blocks), request.teacherScript, tuple(request.promptExamples), tuple(request.studentFlow), request.published)
        try:
            saved = courses.save(course)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.saved", target_type="course", target_id=saved.course_id)
        return course_payload(saved)

    @router.get("/{course_id}/export.html")
    def export_course(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> Response:
        try:
            course = courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.exported", target_type="course", target_id=course_id)
        return Response(export_offline_html(Course(course.course_id, course.title, course.blocks)), media_type="text/html", headers={"Content-Disposition": 'attachment; filename="course.html"'})

    @router.post("/{course_id}/publish")
    def publish_course(course_id: str, request: PublishCourseRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        try:
            courses.publish_to_class(course_id, request.classId, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        return {"courseId": course_id, "classId": request.classId, "status": "published"}

    @router.post("/{course_id}/unpublish")
    def unpublish_course(course_id: str, request: PublishCourseRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        try:
            courses.unpublish_from_class(course_id, request.classId, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.unpublished", target_type="classroom", target_id=request.classId)
        return {"courseId": course_id, "classId": request.classId, "status": "unpublished"}

    @router.delete("/{course_id}")
    def delete_course(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        try:
            courses.delete(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        material_store.delete_for_course(course_id, session.organization_id)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.deleted", target_type="course", target_id=course_id)
        return {"courseId": course_id, "status": "deleted"}

    @router.get("/classrooms/{class_id}/published")
    def list_published_courses(class_id: str, session: SessionContext = Depends(require_session(auth_service))) -> dict[str, object]:
        if session.role == "student":
            user = auth_service.user_for_id(session.user_id)
            if user is None or user.class_id != class_id:
                raise HTTPException(status_code=404, detail="classroom not found")
        return {"courses": [course_payload(course) for course in courses.list_for_class(class_id, session.organization_id)]}

    @router.get("/classrooms/{class_id}/published/{course_id}/materials")
    def list_student_materials(class_id: str, course_id: str, session: SessionContext = Depends(require_session(auth_service))) -> dict[str, list[dict[str, object]]]:
        if session.role != "student":
            raise HTTPException(status_code=403, detail="student access required")
        user = auth_service.user_for_id(session.user_id)
        if user is None or user.class_id != class_id:
            raise HTTPException(status_code=404, detail="classroom not found")
        published = {course.course_id for course in courses.list_for_class(class_id, session.organization_id)}
        if course_id not in published:
            raise HTTPException(status_code=404, detail="course not found")
        return {"materials": [material_payload(material) for material in material_store.list_for_course(course_id, session.organization_id)]}

    @router.post("/{course_id}/materials")
    async def upload_material(course_id: str, file: UploadFile = File(...), session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        filename = file.filename or "course-material"
        content = await file.read()
        try:
            validate_course_material(filename, content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            scan_upload(upload_scanner, content)
        except UnsafeUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        material = material_store.save(course_id, session.organization_id, filename, file.content_type or "", content)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.material_uploaded", target_type="course", target_id=course_id)
        return material_payload(material)

    @router.get("/{course_id}/materials")
    def list_materials(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        try:
            courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        return {"materials": [material_payload(material) for material in material_store.list_for_course(course_id, session.organization_id)]}

    @router.get("/materials/{material_id}/download")
    def download_material(material_id: str, session: SessionContext = Depends(require_session(auth_service))) -> Response:
        try:
            material = material_store.get(material_id, session.organization_id)
            content = material_store.read(material)
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="course material not found") from exc
        if session.role == "student":
            user = auth_service.user_for_id(session.user_id)
            if user is None or not user.class_id:
                raise HTTPException(status_code=404, detail="course material not found")
            published = {course.course_id for course in courses.list_for_class(user.class_id, session.organization_id)}
            if material.course_id not in published:
                raise HTTPException(status_code=404, detail="course material not found")
        return Response(content, media_type=material.content_type, headers={"Content-Disposition": f'attachment; filename="{material.filename}"'})

    @router.delete("/materials/{material_id}")
    def delete_material(material_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        try:
            material_store.delete(material_id, session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="course material not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.material_deleted", target_type="course_material", target_id=material_id)
        return {"materialId": material_id, "status": "deleted"}

    return router


def course_payload(course: CourseRecord) -> dict[str, object]:
    return {"courseId": course.course_id, "title": course.title, "summary": course.summary, "blocks": [{"kind": block.kind, "content": block.content, "authoredBy": block.authored_by} for block in course.blocks], "teacherScript": course.teacher_script, "promptExamples": list(course.prompt_examples), "studentFlow": list(course.student_flow), "published": course.published}


def material_payload(material) -> dict[str, object]:
    return {"materialId": material.material_id, "courseId": material.course_id, "filename": material.filename, "contentType": material.content_type, "size": material.size}
