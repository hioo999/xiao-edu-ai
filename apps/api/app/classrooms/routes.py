from contextlib import nullcontext
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import date, time, datetime

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog

from .assistance import AssistanceManager, TeacherAssignment
from apps.api.app.auth.schedules import AccessSchedule, DailyWindow


class AssistanceRequest(BaseModel):
    studentId: str


class CreateClassroomRequest(BaseModel):
    classId: str
    teacherIds: list[str] = []


class TeacherAssignmentRequest(BaseModel):
    teacherIds: list[str]


class TeacherAssignmentDetail(BaseModel):
    teacherId: str
    role: str = "lead"
    validFrom: datetime | None = None
    validUntil: datetime | None = None


class TeacherAssignmentDetailsRequest(BaseModel):
    assignments: list[TeacherAssignmentDetail]


class EnrollStudentRequest(BaseModel):
    studentId: str
    reason: str = ""


class PresenceRequest(BaseModel):
    activeFeature: str = "home"
    taskState: str = "idle"
    lessonStep: int = 0
    helpNeeded: bool = False


class ScheduleWindowRequest(BaseModel):
    start: time
    end: time


class ClassroomScheduleRequest(BaseModel):
    startDate: date
    endDate: date
    weekdays: set[int] = Field(min_length=1)
    dailyWindows: list[ScheduleWindowRequest] = Field(min_length=1, max_length=8)
    holidayExceptions: set[date] = Field(default_factory=set)


def schedule_payload(schedule: AccessSchedule | None) -> dict[str, object] | None:
    if schedule is None:
        return None
    return {
        "startDate": schedule.start_date.isoformat(),
        "endDate": schedule.end_date.isoformat(),
        "weekdays": sorted(schedule.weekdays),
        "dailyWindows": [{"start": window.start.isoformat(), "end": window.end.isoformat()} for window in schedule.daily_windows],
        "holidayExceptions": sorted(day.isoformat() for day in schedule.holiday_exceptions),
    }


def create_classroom_router(auth_service: AuthService, manager: AssistanceManager, audit_log: AuditLog | None = None, staff_lifecycle=None) -> APIRouter:
    router = APIRouter(prefix="/classrooms", tags=["classrooms"])
    teacher_dependency = require_role(require_session(auth_service), "teacher", "organization_admin", "platform_admin")
    access = TeachingAccess(auth_service, manager)

    def classroom_for(class_id: str, session: SessionContext):
        return access.require_classroom(session, class_id)

    def require_enrollment(class_id: str, student_id: str, session: SessionContext) -> None:
        access.require_student(session, student_id)
        student = auth_service.user_for_id(student_id)
        if student is None or student.class_id != class_id:
            raise HTTPException(status_code=403, detail="student is not enrolled in this classroom")

    @router.get("")
    def list_classrooms(session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        classrooms = manager.classrooms_for_organization(session.organization_id)
        if session.role == "teacher":
            classrooms = [item for item in classrooms if session.user_id in item.teachers]
        return {"classrooms": [{
            "classId": classroom.class_id,
            "state": classroom.state,
            "teacherCount": len(classroom.teachers),
            "onlineStudents": len(manager.students_for_classroom(classroom.class_id)),
            "helpNeeded": sum(student.help_needed for student in manager.students_for_classroom(classroom.class_id)),
        } for classroom in classrooms]}

    @router.post("")
    def create_classroom(request: CreateClassroomRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            if session.role == "teacher":
                teacher_ids = {session.user_id}
            else:
                teacher_ids = {teacher_id for teacher_id in request.teacherIds if teacher_id.strip()}
                if not all(auth_service.has_active_role(teacher_id, session.organization_id, "teacher") for teacher_id in teacher_ids):
                    raise HTTPException(status_code=422, detail="teacher account is not in this organization")
            try:
                classroom = manager.create(request.classId, session.organization_id)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail="classroom already exists") from exc
            classroom.teachers = teacher_ids
            manager._persist(classroom)
            if audit_log:
                audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.created", target_type="classroom", target_id=classroom.class_id)
            return {"classId": classroom.class_id, "state": classroom.state}

    @router.get("/{class_id}")
    def get_classroom(class_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        classroom = classroom_for(class_id, session)
        return {"classId": classroom.class_id, "state": classroom.state, "teacherCount": len(classroom.teachers), "schedule": schedule_payload(classroom.schedule), "activeAssistance": [{"studentId": grant.student_id, "teacherId": grant.teacher_id} for grant in manager.grants.values() if grant.class_id == class_id]}

    @router.get("/{class_id}/students")
    def list_students(class_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, list[dict[str, object]]]:
        classroom_for(class_id, session)
        return {"students": [{"studentId": presence.student_id, "activeFeature": presence.active_feature, "taskState": presence.task_state, "lessonStep": presence.lesson_step, "helpNeeded": presence.help_needed, "assistanceGranted": manager.can_act_as(class_id, session.user_id, presence.student_id)} for presence in manager.students_for_classroom(class_id)]}

    @router.get("/{class_id}/students/{student_id}/view")
    def student_view(class_id: str, student_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        classroom_for(class_id, session)
        require_enrollment(class_id, student_id, session)
        if session.role == "teacher" and session.user_id not in manager.classrooms[class_id].teachers:
            raise HTTPException(status_code=403, detail="teacher is not assigned to this classroom")
        if not manager.can_act_as(class_id, session.user_id, student_id):
            raise HTTPException(status_code=403, detail="student assistance is not granted")
        presence = next((item for item in manager.students_for_classroom(class_id) if item.student_id == student_id), None)
        if presence is None:
            raise HTTPException(status_code=404, detail="student presence not found")
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.student_view_opened", target_type="student", target_id=student_id)
        return {
            "classId": class_id,
            "studentId": student_id,
            "mode": "assisted_view",
            "readOnly": False,
            "activeFeature": presence.active_feature,
            "taskState": presence.task_state,
            "lessonStep": presence.lesson_step,
            "helpNeeded": presence.help_needed,
        }

    @router.post("/{class_id}/open")
    def open_classroom(class_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        classroom = classroom_for(class_id, session)
        if session.role == "teacher" and session.user_id not in classroom.teachers:
            raise HTTPException(status_code=403, detail="teacher is not assigned to this classroom")
        manager.open(class_id)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.opened", target_type="classroom", target_id=class_id)
        return {"classId": class_id, "state": "open"}

    @router.post("/{class_id}/pause")
    def pause_classroom(class_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        classroom = classroom_for(class_id, session)
        if session.role == "teacher" and session.user_id not in classroom.teachers:
            raise HTTPException(status_code=403, detail="teacher is not assigned to this classroom")
        classroom.state = "paused"
        manager._persist(classroom)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.paused", target_type="classroom", target_id=class_id)
        return {"classId": class_id, "state": "paused"}

    @router.post("/{class_id}/close")
    def close_classroom(class_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        classroom = classroom_for(class_id, session)
        if session.role == "teacher" and session.user_id not in classroom.teachers:
            raise HTTPException(status_code=403, detail="teacher is not assigned to this classroom")
        manager.close(class_id)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.closed", target_type="classroom", target_id=class_id)
        return {"classId": class_id, "state": "closed"}

    @router.put("/{class_id}/schedule")
    def save_schedule(class_id: str, request: ClassroomScheduleRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        classroom = classroom_for(class_id, session)
        if session.role == "teacher" and session.user_id not in classroom.teachers:
            raise HTTPException(status_code=403, detail="teacher is not assigned to this classroom")
        if request.endDate < request.startDate or any(day < 0 or day > 6 for day in request.weekdays) or any(window.end <= window.start for window in request.dailyWindows):
            raise HTTPException(status_code=422, detail="invalid classroom schedule")
        schedule = AccessSchedule(
            start_date=request.startDate,
            end_date=request.endDate,
            weekdays=request.weekdays,
            daily_windows=tuple(DailyWindow(window.start, window.end) for window in request.dailyWindows),
            holiday_exceptions=request.holidayExceptions,
        )
        manager.set_schedule(class_id, schedule)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.schedule_saved", target_type="classroom", target_id=class_id)
        return {"classId": class_id, "schedule": schedule_payload(schedule)}

    @router.put("/{class_id}/teachers")
    def assign_teachers(class_id: str, request: TeacherAssignmentRequest, session: SessionContext = Depends(require_role(require_session(auth_service), "organization_admin", "platform_admin"))) -> dict[str, object]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            classroom = classroom_for(class_id, session)
            teacher_ids = {teacher_id for teacher_id in request.teacherIds if teacher_id.strip()}
            if not teacher_ids:
                raise HTTPException(status_code=422, detail="at least one teacher is required")
            if not all(auth_service.has_active_role(teacher_id, session.organization_id, "teacher") for teacher_id in teacher_ids):
                raise HTTPException(status_code=422, detail="teacher account is not in this organization")
            manager.assign_teachers(classroom.class_id, teacher_ids)
            if audit_log:
                audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.teachers_assigned", target_type="classroom", target_id=class_id)
            return {"classId": class_id, "teacherIds": sorted(teacher_ids)}

    @router.get("/{class_id}/staff")
    def list_classroom_staff(class_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        classroom_for(class_id, session)
        assignments = manager.assignments_for_class(class_id)
        if not assignments:
            assignments = [TeacherAssignment(class_id, teacher_id) for teacher_id in sorted(manager.classrooms[class_id].teachers)]
        return {"assignments": [{"teacherId": item.teacher_id, "role": item.role, "validFrom": item.valid_from.isoformat() if item.valid_from else None, "validUntil": item.valid_until.isoformat() if item.valid_until else None} for item in assignments]}

    @router.put("/{class_id}/staff")
    def update_classroom_staff(class_id: str, request: TeacherAssignmentDetailsRequest, session: SessionContext = Depends(require_role(require_session(auth_service), "organization_admin", "platform_admin"))) -> dict[str, object]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            classroom = classroom_for(class_id, session)
            if not request.assignments:
                raise HTTPException(status_code=422, detail="at least one teacher assignment is required")
            if any(item.role not in {"lead", "assistant", "substitute"} or (item.validFrom and item.validUntil and item.validUntil <= item.validFrom) for item in request.assignments):
                raise HTTPException(status_code=422, detail="invalid teacher assignment")
            teacher_ids = {item.teacherId for item in request.assignments}
            if not all(auth_service.has_active_role(item, session.organization_id, "teacher") for item in teacher_ids):
                raise HTTPException(status_code=422, detail="teacher account is not in this organization")
            assignments = manager.set_teacher_assignments(class_id, [TeacherAssignment(class_id, item.teacherId, item.role, item.validFrom, item.validUntil) for item in request.assignments])
            manager.assign_teachers(class_id, teacher_ids)
            return {"classId": classroom.class_id, "assignments": [{"teacherId": item.teacher_id, "role": item.role, "validFrom": item.valid_from.isoformat() if item.valid_from else None, "validUntil": item.valid_until.isoformat() if item.valid_until else None} for item in assignments]}

    @router.post("/{class_id}/members")
    def enroll_student(class_id: str, request: EnrollStudentRequest, session: SessionContext = Depends(require_role(require_session(auth_service), "organization_admin", "platform_admin"))) -> dict[str, object]:
        with (staff_lifecycle.lock if staff_lifecycle else nullcontext()):
            if staff_lifecycle:
                staff_lifecycle.require_active_session(session)
            classroom = classroom_for(class_id, session)
            student = auth_service.user_for_id(request.studentId)
            if student is None or student.role != "student" or student.organization_id != classroom.organization_id:
                raise HTTPException(status_code=404, detail="student not found")
            previous = manager.active_class_for_student(student.user_id) or student.class_id
            record = manager.enroll_student(student.user_id, student.organization_id, class_id, reason=request.reason)
            auth_service.set_class(student.user_id, student.organization_id, class_id)
            return {"studentId": student.user_id, "classId": record.class_id, "previousClassId": previous if previous != class_id else None, "joinedAt": record.joined_at.isoformat()}

    @router.get("/students/{student_id}/memberships")
    def student_memberships(student_id: str, session: SessionContext = Depends(teacher_dependency)) -> dict[str, object]:
        student = auth_service.user_for_id(student_id)
        if student is None or student.organization_id != session.organization_id:
            raise HTTPException(status_code=404, detail="student not found")
        if session.role == "teacher" and not access.can_manage_student(session, student_id):
            raise HTTPException(status_code=403, detail="student access denied")
        return {"memberships": [{"classId": item.class_id, "active": item.left_at is None, "joinedAt": item.joined_at.isoformat(), "leftAt": item.left_at.isoformat() if item.left_at else None, "reason": item.reason} for item in manager.memberships_for_student(student_id)]}

    @router.post("/{class_id}/assistance")
    def grant_assistance(class_id: str, request: AssistanceRequest, session: SessionContext = Depends(teacher_dependency)) -> dict[str, str]:
        classroom_for(class_id, session)
        require_enrollment(class_id, request.studentId, session)
        try:
            grant = manager.grant_assistance(class_id, teacher_id=session.user_id, student_id=request.studentId)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="teacher assistance is not allowed") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="classroom.assistance_granted", target_type="student", target_id=request.studentId)
        return {"classId": grant.class_id, "teacherId": grant.teacher_id, "studentId": grant.student_id}

    @router.post("/{class_id}/presence")
    def report_presence(class_id: str, request: PresenceRequest, session: SessionContext = Depends(require_session(auth_service))) -> dict[str, object]:
        classroom = manager.classrooms.get(class_id)
        if classroom is None or classroom.organization_id != session.organization_id:
            raise HTTPException(status_code=404, detail="classroom not found")
        if session.role != "student":
            raise HTTPException(status_code=403, detail="only students can report presence")
        access.require_classroom(session, class_id)
        try:
            presence = manager.report_presence(class_id, session.user_id, active_feature=request.activeFeature, task_state=request.taskState, lesson_step=request.lessonStep, help_needed=request.helpNeeded)
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"studentId": presence.student_id, "activeFeature": presence.active_feature, "taskState": presence.task_state, "lessonStep": presence.lesson_step, "helpNeeded": presence.help_needed}

    return router
