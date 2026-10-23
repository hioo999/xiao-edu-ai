from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
import uuid

from fastapi import HTTPException

from apps.api.app.audit.service import AuditLog
from apps.api.app.auth.schedules import SHANGHAI
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.courses.catalog import CourseCatalog
from .service import AuthService


def normalize_account_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return (value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value).astimezone(timezone.utc)


class StaffLifecycle:
    def __init__(self, auth, classrooms=None, courses=None, audit=None):
        self.auth, self.classrooms, self.courses, self.audit = auth, classrooms, courses, audit
        self.lock = RLock()
        self._history = []

    def staff(self, organization_id: str, username: str):
        user = next((user for name, user in self.auth.users_for_organization(organization_id) if name == username), None)
        if user is None or user.role not in {"teacher", "organization_admin"}:
            raise HTTPException(status_code=404, detail="staff account not found")
        return user

    def plan(self, organization_id: str, username: str) -> dict:
        user = self.staff(organization_id, username)
        if self.classrooms is None or self.courses is None:
            raise HTTPException(status_code=503, detail="teaching lifecycle storage is unavailable")
        return {
            "sourceUserId": user.user_id,
            "classIds": sorted(item.class_id for item in self.classrooms.classrooms_for_organization(organization_id) if user.user_id in item.teachers),
            "courseIds": sorted(item.course_id for item in self.courses.list_for_organization(organization_id) if item.author_user_id == user.user_id),
        }

    def require_active_session(self, actor):
        current_actor = self.auth.user_for_id(actor.user_id)
        if current_actor is None or current_actor.role != actor.role or not current_actor.enabled or (current_actor.expires_at and current_actor.expires_at <= datetime.now(timezone.utc)):
            raise HTTPException(status_code=403, detail="account is no longer active")
        return current_actor

    def validate_change(self, organization_id, username, actor, *, deactivating=False):
        current_actor = self.require_active_session(actor)
        if current_actor.role not in {"platform_admin", "organization_admin"} or (current_actor.role != "platform_admin" and current_actor.organization_id != organization_id):
            raise HTTPException(status_code=403, detail="administrator access denied")
        user = next((user for name, user in self.auth.users_for_organization(organization_id) if name == username), None)
        if user is None:
            raise HTTPException(status_code=404, detail="account not found")
        if user.role == "platform_admin":
            raise HTTPException(status_code=403, detail="platform administrator cannot be managed here")
        if user.user_id == actor.user_id:
            raise HTTPException(status_code=409, detail="cannot perform this operation on your own account")
        if deactivating and user.role == "teacher":
            plan = self.plan(organization_id, username)
            if plan["classIds"] or plan["courseIds"]:
                raise HTTPException(status_code=409, detail="teacher has assigned classes or courses; complete handover first")
        return user

    def revoke_assistance(self, user_id: str) -> None:
        if self.classrooms is not None:
            self.classrooms.revoke_teacher_assistance(user_id)

    def _database(self) -> Path | None:
        repositories = (self.auth, self.classrooms, self.courses)
        if any(type(repository) is not expected for repository, expected in zip(repositories, (AuthService, AssistanceManager, CourseCatalog))):
            raise HTTPException(status_code=503, detail="atomic staff handover requires the SQLite or in-memory adapter")
        paths = [repository.storage_path.resolve() if repository.storage_path else None for repository in repositories]
        if len(set(paths)) != 1:
            raise HTTPException(status_code=503, detail="staff handover requires one shared SQLite database")
        if self.audit is not None and type(self.audit) is not AuditLog:
            raise HTTPException(status_code=503, detail="atomic staff handover requires the SQLite audit adapter")
        if self.audit and self.audit.storage_path and self.audit.storage_path.resolve() != paths[0]:
            raise HTTPException(status_code=503, detail="staff audit must use the shared SQLite database")
        return paths[0]

    def handover(self, organization_id, username, replacement_id, actor, reason) -> dict:
        with self.lock:
            source = self.staff(organization_id, username)
            self.validate_change(organization_id, username, actor)
            if source.role != "teacher" or source.user_id == actor.user_id:
                raise HTTPException(status_code=422, detail="only another teacher can be handed over")
            target = self.auth.user_for_id(replacement_id)
            if target is None or target.role != "teacher" or target.organization_id != organization_id or target.user_id == source.user_id or not target.enabled or (target.expires_at and target.expires_at <= datetime.now(timezone.utc)):
                raise HTTPException(status_code=422, detail="replacement must be a different active teacher in this organization")
            database = self._database()
            record = {"handoverId": uuid.uuid4().hex, "sourceUserId": source.user_id, "replacementUserId": target.user_id, "actorId": actor.user_id, "reason": reason, "sourceDisabled": True, "createdAt": datetime.now(timezone.utc).isoformat()}
            if database:
                try:
                    with sqlite3.connect(database) as connection:
                        connection.execute("begin immediate")
                        current_target = connection.execute("select enabled, expires_at from platform_users where user_id = ? and organization_id = ? and role = 'teacher'", (target.user_id, organization_id)).fetchone()
                        if current_target is None or not current_target[0] or (current_target[1] and datetime.fromisoformat(current_target[1]) <= datetime.now(timezone.utc)):
                            raise HTTPException(status_code=422, detail="replacement teacher is no longer active")
                        classroom_rows = connection.execute("select class_id, teachers from classrooms where organization_id = ?", (organization_id,)).fetchall()
                        assignments = {class_id: (set(json.loads(teachers)) - {source.user_id}) | {target.user_id} for class_id, teachers in classroom_rows if source.user_id in set(json.loads(teachers))}
                        course_ids = [row[0] for row in connection.execute("select course_id from courses where organization_id = ? and author_user_id = ? order by course_id", (organization_id, source.user_id))]
                        record.update(classIds=sorted(assignments), courseIds=course_ids)
                        if not assignments and not course_ids:
                            raise HTTPException(status_code=409, detail="teacher has no teaching resources to hand over")
                        for class_id, teachers in assignments.items():
                            connection.execute("update classrooms set teachers = ? where class_id = ? and organization_id = ?", (json.dumps(sorted(teachers)), class_id, organization_id))
                        connection.execute("update courses set author_user_id = ? where organization_id = ? and author_user_id = ?", (target.user_id, organization_id, source.user_id))
                        connection.execute("update platform_users set enabled = 0 where organization_id = ? and user_id = ?", (organization_id, source.user_id))
                        connection.execute("delete from access_sessions where user_id = ?", (source.user_id,))
                        connection.execute("create table if not exists staff_handovers (handover_id text primary key, organization_id text not null, source_user_id text not null, payload text not null)")
                        connection.execute("insert into staff_handovers values (?, ?, ?, ?)", (record["handoverId"], organization_id, source.user_id, json.dumps(record, ensure_ascii=False)))
                        if self.audit and self.audit.storage_path:
                            connection.execute("insert into audit_records (organization_id, actor_id, action, target_type, target_id, created_at) values (?, ?, ?, ?, ?, ?)", (organization_id, actor.user_id, "staff.handover_completed", "staff", source.user_id, record["createdAt"]))
                except sqlite3.Error as exc:
                    raise HTTPException(status_code=503, detail="handover failed; no teaching resources were changed") from exc
                self.auth.refresh_from_storage()
                self.classrooms.refresh_from_storage()
                self.courses.refresh_from_storage()
                if self.audit and self.audit.storage_path:
                    self.audit.refresh_from_storage()
            else:
                record.update(self.plan(organization_id, username))
                if not record["classIds"] and not record["courseIds"]:
                    raise HTTPException(status_code=409, detail="teacher has no teaching resources to hand over")
                for class_id in record["classIds"]:
                    self.classrooms.assign_teachers(class_id, (self.classrooms.classrooms[class_id].teachers - {source.user_id}) | {target.user_id})
                for course_id in record["courseIds"]:
                    self.courses.save(replace(self.courses.get(course_id, organization_id), author_user_id=target.user_id))
                self.auth.set_enabled(username, organization_id, False)
                self._history.append((organization_id, record))
            self.revoke_assistance(source.user_id)
            if self.audit and not self.audit.storage_path:
                self.audit.record(organization_id=organization_id, actor_id=actor.user_id, action="staff.handover_completed", target_type="staff", target_id=source.user_id)
            return record

    def history(self, organization_id, username):
        source = self.staff(organization_id, username)
        database = self._database()
        if database:
            with sqlite3.connect(database) as connection:
                if connection.execute("select 1 from sqlite_master where name = 'staff_handovers' and type = 'table'").fetchone() is None:
                    return []
                return [json.loads(row[0]) for row in connection.execute("select payload from staff_handovers where organization_id = ? and source_user_id = ? order by rowid desc", (organization_id, source.user_id))]
        return [record for organization, record in reversed(self._history) if organization == organization_id and record["sourceUserId"] == source.user_id]
