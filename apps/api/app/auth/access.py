from fastapi import HTTPException

from apps.api.app.classrooms.assistance import AssistanceManager
from .service import AuthService, SessionContext


class TeachingAccess:
    def __init__(self, auth: AuthService, classrooms: AssistanceManager | None) -> None:
        self.auth = auth
        self.classrooms = classrooms

    def teacher_class_ids(self, session: SessionContext) -> set[str]:
        if self.classrooms is None:
            return set()
        return {
            classroom.class_id
            for classroom in self.classrooms.classrooms_for_organization(session.organization_id)
            if self.classrooms.teacher_is_assigned(classroom.class_id, session.user_id)
        }

    def require_classroom(self, session: SessionContext, class_id: str):
        classroom = self.classrooms.classrooms.get(class_id) if self.classrooms else None
        if classroom is None or (session.role != "platform_admin" and classroom.organization_id != session.organization_id):
            raise HTTPException(status_code=404, detail="classroom not found")
        if session.role == "teacher" and class_id not in self.teacher_class_ids(session):
            raise HTTPException(status_code=403, detail="teacher is not assigned to this classroom")
        if session.role == "student":
            user = self.auth.user_for_id(session.user_id)
            if user is None or user.class_id != class_id:
                raise HTTPException(status_code=403, detail="student is not enrolled in this classroom")
        return classroom

    def can_manage_student(self, session: SessionContext, student_id: str) -> bool:
        student = self.auth.user_for_id(student_id)
        if student is None or student.role != "student":
            return False
        if session.role == "platform_admin":
            return True
        if student.organization_id != session.organization_id:
            return False
        if session.role == "organization_admin":
            return True
        if session.role != "teacher":
            return False
        class_id = self.classrooms.active_class_for_student(student_id) if self.classrooms else None
        return (class_id or student.class_id) in self.teacher_class_ids(session)

    def require_student(self, session: SessionContext, student_id: str) -> None:
        if not self.can_manage_student(session, student_id):
            raise HTTPException(status_code=403, detail="student access denied")

    def require_class_membership(self, session: SessionContext, class_id: str, student_id: str) -> None:
        if session.role in {"platform_admin", "organization_admin"}:
            student = self.auth.user_for_id(student_id)
            if student is None or student.organization_id != session.organization_id:
                raise HTTPException(status_code=403, detail="student access denied")
            return
        self.require_classroom(session, class_id)
        if self.classrooms and self.classrooms.active_class_for_student(student_id) == class_id:
            return
        student = self.auth.user_for_id(student_id)
        if student is None or student.class_id != class_id:
            raise HTTPException(status_code=403, detail="student is not enrolled in this classroom")
