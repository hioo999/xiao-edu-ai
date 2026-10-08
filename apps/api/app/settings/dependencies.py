from collections.abc import Callable

from fastapi import Depends, HTTPException

from apps.api.app.auth.service import SessionContext
from apps.api.app.auth.service import AuthService
from apps.api.app.classrooms.assistance import AssistanceManager

from .service import SettingsStore


def require_student_creative_access(session_dependency, store: SettingsStore, auth_service: AuthService | None = None, classrooms: AssistanceManager | None = None) -> Callable[[SessionContext], SessionContext]:
    def dependency(session: SessionContext = Depends(session_dependency)) -> SessionContext:
        if session.role == "student":
            settings = store.get(session.organization_id)
            if not settings.student_home_enabled:
                message = settings.maintenance_message or "创作大厅正在维护，请稍后再来。"
                raise HTTPException(status_code=423, detail=message)
            user = auth_service.user_for_id(session.user_id) if auth_service else None
            if classrooms and user and user.class_id and not classrooms.student_creative_access_allowed(user.class_id):
                raise HTTPException(status_code=423, detail="当前不在班级开放时段，暂时不能进行 AI 创作。")
        return session

    return dependency
