from contextlib import nullcontext
from dataclasses import replace
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.classrooms.assistance import AssistanceManager
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
    lessons: list[dict[str, object]] = []

class PublishCourseRequest(BaseModel):
    classId: str

class ReviewRequest(BaseModel):
    note: str = ""


def create_course_router(auth_service: AuthService, material_store: CourseMaterialStore, catalog: CourseCatalog | None = None, audit_log: AuditLog | None = None, classrooms: AssistanceManager | None = None, staff_lifecycle=None) -> APIRouter:
    router = APIRouter(prefix="/courses", tags=["courses"])
    teacher_dependency = require_role(require_session(auth_service), "teacher", "organization_admin", "platform_admin")
    courses = catalog or CourseCatalog()
    upload_scanner = build_upload_scanner()
    access = TeachingAccess(auth_service, classrooms)

    def can_read_course(course: CourseRecord, session: SessionContext) -> bool:
        if session.role != "teacher" or course.author_user_id == session.user_id:
            return True
        return any(course.course_id == published.course_id for class_id in access.teacher_class_ids(session) for published in courses.list_for_class(class_id, session.organization_id))

    def checked_course(course_id: str, session: SessionContext, *, write: bool = False) -> CourseRecord:
        course = courses.get(course_id, session.organization_id)
        if session.role == "teacher" and ((write and course.author_user_id != session.user_id) or not can_read_course(course, session)):
            raise HTTPException(status_code=403, detail="course access denied")
        return course

    @router.get("")
    def list_courses(session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        return {"courses": [course_payload(course) for course in courses.list_for_organization(session.organization_id) if can_read_course(course, session)]}

    @router.get("/{course_id}")
    def get_course(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            return course_payload(checked_course(course_id, session))
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc

    @router.post("")
    def save_course(request: CourseRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            allowed_kinds = {"text", "image", "video", "code", "attachment", "interaction", "step", "challenge"}
            if any(block.kind not in allowed_kinds or block.authoredBy not in {"teacher", "ai"} for block in request.blocks):
                raise HTTPException(status_code=422, detail="unsupported course block")
            if not request.title.strip():
                raise HTTPException(status_code=422, detail="course title is required")
            lesson_ids: set[str] = set()
            normalized_lessons: list[dict[str, object]] = []
            for index, lesson in enumerate(request.lessons):
                lesson_id = str(lesson.get("lessonId", "")).strip()
                title = str(lesson.get("title", "")).strip()
                if not lesson_id or not title:
                    raise HTTPException(status_code=422, detail="each lesson needs an id and title")
                if lesson_id in lesson_ids:
                    raise HTTPException(status_code=422, detail="lesson ids must be unique")
                lesson_ids.add(lesson_id)
                normalized_lessons.append({**lesson, "lessonId": lesson_id, "title": title, "sortOrder": index})
            author_user_id = session.user_id
            try:
                author_user_id = checked_course(request.courseId, session, write=True).author_user_id
            except KeyError:
                pass
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail="course access denied") from exc
            existing = courses.get(request.courseId, session.organization_id) if request.courseId in {item.course_id for item in courses.list_for_organization(session.organization_id)} else None
            if existing is not None:
                removed_lesson_ids = {str(lesson.get("lessonId")) for lesson in existing.lessons} - lesson_ids
                bound_lesson_ids = {str(material.lesson_id) for material in material_store.list_for_course(request.courseId, session.organization_id) if material.lesson_id}
                if removed_lesson_ids & bound_lesson_ids:
                    raise HTTPException(status_code=422, detail="cannot remove a lesson with bound materials")
            lessons = tuple(normalized_lessons) or tuple({"lessonId": f"{request.courseId}-lesson-{index + 1}", "title": title, "content": request.blocks[index].content if index < len(request.blocks) else title, "sortOrder": index, "required": True} for index, title in enumerate(request.studentFlow or [block.content for block in request.blocks]))
            course = CourseRecord(request.courseId, session.organization_id, author_user_id, request.title.strip(), request.summary.strip(), tuple(LessonBlock(kind=block.kind, content=block.content, authored_by=block.authoredBy) for block in request.blocks), request.teacherScript, tuple(request.promptExamples), tuple(request.studentFlow), request.published, existing.review_status if existing else "draft", existing.review_note if existing else "", lessons)
            try:
                saved = courses.save(course)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            if audit_log:
                audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.saved", target_type="course", target_id=saved.course_id)
            return course_payload(saved)

    @router.post("/{course_id}/submit-review")
    def submit_review(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            course = checked_course(course_id, session, write=True)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        if not course.title.strip() or not (course.blocks or course.student_flow):
            raise HTTPException(status_code=422, detail="course needs title and lesson content before review")
        saved = courses.save(replace(course, published=False, review_status="pending_review", review_note=""))
        return course_payload(saved)

    @router.get("/admin/review")
    def review_queue(session: SessionContext = Depends(require_role(require_session(auth_service), "organization_admin", "platform_admin"))) -> dict[str, object]:
        return {"courses": [course_payload(course) for course in courses.list_for_organization(session.organization_id) if course.review_status == "pending_review"]}

    @router.post("/{course_id}/review/approve")
    def approve_review(course_id: str, request: ReviewRequest, session: SessionContext = Depends(require_role(require_session(auth_service), "organization_admin", "platform_admin"))) -> dict[str, object]:
        try: course = courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc: raise HTTPException(status_code=404, detail="course not found") from exc
        saved = courses.save(replace(course, published=False, review_status="approved", review_note=request.note))
        return course_payload(saved)

    @router.post("/{course_id}/review/reject")
    def reject_review(course_id: str, request: ReviewRequest, session: SessionContext = Depends(require_role(require_session(auth_service), "organization_admin", "platform_admin"))) -> dict[str, object]:
        try: course = courses.get(course_id, session.organization_id)
        except (KeyError, PermissionError) as exc: raise HTTPException(status_code=404, detail="course not found") from exc
        saved = courses.save(replace(course, published=False, review_status="rejected", review_note=request.note))
        return course_payload(saved)

    @router.get("/{course_id}/export.html")
    def export_course(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> Response:
        try:
            course = checked_course(course_id, session)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.exported", target_type="course", target_id=course_id)
        return Response(export_offline_html(Course(course.course_id, course.title, course.blocks)), media_type="text/html", headers={"Content-Disposition": 'attachment; filename="course.html"'})

    @router.get("/{course_id}/lessons")
    def list_lessons(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            course = checked_course(course_id, session)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        lessons = [{**lesson, "courseId": course.course_id} for lesson in course.lessons]
        return {"courseId": course.course_id, "lessons": lessons}

    @router.post("/{course_id}/publish")
    def publish_course(course_id: str, request: PublishCourseRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            try:
                checked_course(course_id, session)
                access.require_classroom(session, request.classId)
                courses.publish_to_class(course_id, request.classId, session.organization_id)
            except (KeyError, PermissionError) as exc:
                raise HTTPException(status_code=404, detail="course not found") from exc
            return {"courseId": course_id, "classId": request.classId, "status": "published"}

    @router.post("/{course_id}/unpublish")
    def unpublish_course(course_id: str, request: PublishCourseRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            try:
                checked_course(course_id, session)
                access.require_classroom(session, request.classId)
                courses.unpublish_from_class(course_id, request.classId, session.organization_id)
            except (KeyError, PermissionError) as exc:
                raise HTTPException(status_code=404, detail="course not found") from exc
            if audit_log:
                audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.unpublished", target_type="classroom", target_id=request.classId)
            return {"courseId": course_id, "classId": request.classId, "status": "unpublished"}

    @router.delete("/{course_id}")
    def delete_course(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            try:
                checked_course(course_id, session, write=True)
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
        else:
            access.require_classroom(session, class_id)
        return {"courses": [course_payload(course, include_teacher_script=session.role != "student") for course in courses.list_for_class(class_id, session.organization_id)]}

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
    async def upload_material(course_id: str, file: UploadFile = File(...), lessonId: str | None = None, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        try:
            course = checked_course(course_id, session, write=True)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="course not found") from exc
        if lessonId and lessonId not in {str(lesson.get("lessonId")) for lesson in course.lessons}:
            raise HTTPException(status_code=422, detail="lesson not found in course")
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
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            try:
                checked_course(course_id, session, write=True)
            except (KeyError, PermissionError) as exc:
                raise HTTPException(status_code=404, detail="course not found") from exc
            material = material_store.save(course_id, session.organization_id, filename, file.content_type or "", content, lessonId)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.material_uploaded", target_type="course", target_id=course_id)
        return material_payload(material)

    @router.get("/{course_id}/materials")
    def list_materials(course_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        try:
            checked_course(course_id, session)
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
        else:
            try:
                checked_course(material.course_id, session)
            except (KeyError, PermissionError) as exc:
                raise HTTPException(status_code=404, detail="course material not found") from exc
        return Response(content, media_type=material.content_type, headers={"Content-Disposition": f'attachment; filename="{material.filename}"'})

    @router.delete("/materials/{material_id}")
    def delete_material(material_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            try:
                material = material_store.get(material_id, session.organization_id)
                checked_course(material.course_id, session, write=True)
                material_store.delete(material_id, session.organization_id)
            except (KeyError, PermissionError) as exc:
                raise HTTPException(status_code=404, detail="course material not found") from exc
            if audit_log:
                audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="course.material_deleted", target_type="course_material", target_id=material_id)
            return {"materialId": material_id, "status": "deleted"}

    return router


def course_payload(course: CourseRecord, *, include_teacher_script: bool = True) -> dict[str, object]:
    payload = {"courseId": course.course_id, "title": course.title, "summary": course.summary, "blocks": [{"kind": block.kind, "content": block.content, "authoredBy": block.authored_by} for block in course.blocks], "promptExamples": list(course.prompt_examples), "studentFlow": list(course.student_flow), "lessons": list(course.lessons), "published": course.published, "reviewStatus": course.review_status, "reviewNote": course.review_note}
    if include_teacher_script:
        payload["teacherScript"] = course.teacher_script
    return payload


def material_payload(material) -> dict[str, object]:
    return {"materialId": material.material_id, "courseId": material.course_id, "lessonId": material.lesson_id, "filename": material.filename, "contentType": material.content_type, "size": material.size}
