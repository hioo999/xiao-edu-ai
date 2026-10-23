from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from apps.api.app.auth.schedules import AccessSchedule, DailyWindow, SHANGHAI, is_access_allowed


class ClassroomState(StrEnum):
    PAUSED = "paused"
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Classroom:
    class_id: str
    organization_id: str
    state: ClassroomState = ClassroomState.PAUSED
    teachers: set[str] = field(default_factory=lambda: {"teacher-001"})
    schedule: AccessSchedule | None = None


@dataclass(frozen=True)
class AssistanceGrant:
    class_id: str
    teacher_id: str
    student_id: str


@dataclass(frozen=True)
class AuditEvent:
    action: str
    actor_id: str
    target_id: str


@dataclass
class StudentPresence:
    student_id: str
    active_feature: str = "home"
    task_state: str = "idle"
    lesson_step: int = 0
    help_needed: bool = False


@dataclass(frozen=True)
class MembershipRecord:
    student_id: str
    organization_id: str
    class_id: str
    joined_at: datetime
    left_at: datetime | None = None
    reason: str = ""


@dataclass(frozen=True)
class TeacherAssignment:
    class_id: str
    teacher_id: str
    role: str = "lead"
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    def active(self, now: datetime | None = None) -> bool:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        start = self.valid_from and self.valid_from.astimezone(timezone.utc)
        end = self.valid_until and self.valid_until.astimezone(timezone.utc)
        return (start is None or current >= start) and (end is None or current < end)


class AssistanceManager:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.classrooms: dict[str, Classroom] = {}
        self.grants: dict[tuple[str, str, str], AssistanceGrant] = {}
        self.audit_events: list[AuditEvent] = []
        self.presence: dict[tuple[str, str], StudentPresence] = {}
        self.memberships: list[MembershipRecord] = []
        self.teacher_assignments: list[TeacherAssignment] = []
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("create table if not exists classrooms (class_id text primary key, organization_id text not null, state text not null, teachers text not null)")
                connection.execute("create table if not exists classroom_memberships (student_id text not null, organization_id text not null, class_id text not null, joined_at text not null, left_at text, reason text not null default '', primary key (student_id, joined_at))")
                connection.execute("create table if not exists classroom_teacher_assignments (class_id text not null, teacher_id text not null, role text not null, valid_from text, valid_until text, primary key (class_id, teacher_id, role, valid_from))")
                columns = {row[1] for row in connection.execute("pragma table_info(classrooms)")}
                if "schedule" not in columns:
                    connection.execute("alter table classrooms add column schedule text")
                rows = connection.execute("select class_id, organization_id, state, teachers, schedule from classrooms").fetchall()
                self._load_lifecycle(connection)
            self.classrooms = {row[0]: Classroom(row[0], row[1], ClassroomState(row[2]), set(json.loads(row[3])), self._deserialize_schedule(row[4])) for row in rows}

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    def _load_lifecycle(self, connection) -> None:
        self.memberships = [MembershipRecord(row[0], row[1], row[2], datetime.fromisoformat(row[3]), self._parse_dt(row[4]), row[5]) for row in connection.execute("select student_id, organization_id, class_id, joined_at, left_at, reason from classroom_memberships order by joined_at desc")]
        self.teacher_assignments = [TeacherAssignment(row[0], row[1], row[2], self._parse_dt(row[3]), self._parse_dt(row[4])) for row in connection.execute("select class_id, teacher_id, role, valid_from, valid_until from classroom_teacher_assignments")]

    def _persist_lifecycle(self) -> None:
        if not self._storage_path:
            return
        with sqlite3.connect(self._storage_path) as connection:
            connection.execute("delete from classroom_memberships")
            connection.executemany("insert into classroom_memberships values (?, ?, ?, ?, ?, ?)", [(item.student_id, item.organization_id, item.class_id, item.joined_at.isoformat(), item.left_at.isoformat() if item.left_at else None, item.reason) for item in self.memberships])
            connection.execute("delete from classroom_teacher_assignments")
            connection.executemany("insert into classroom_teacher_assignments values (?, ?, ?, ?, ?)", [(item.class_id, item.teacher_id, item.role, item.valid_from.isoformat() if item.valid_from else None, item.valid_until.isoformat() if item.valid_until else None) for item in self.teacher_assignments])

    def enroll_student(self, student_id: str, organization_id: str, class_id: str, *, reason: str = "") -> MembershipRecord:
        current = next((item for item in self.memberships if item.student_id == student_id and item.left_at is None), None)
        now = datetime.now(timezone.utc)
        if current and current.class_id == class_id:
            return current
        if current:
            self.memberships = [item if item is not current else MembershipRecord(item.student_id, item.organization_id, item.class_id, item.joined_at, now, item.reason) for item in self.memberships]
        record = MembershipRecord(student_id, organization_id, class_id, now, None, reason)
        self.memberships.insert(0, record)
        self._persist_lifecycle()
        return record

    def memberships_for_student(self, student_id: str) -> list[MembershipRecord]:
        return [item for item in self.memberships if item.student_id == student_id]

    def active_class_for_student(self, student_id: str) -> str | None:
        record = next((item for item in self.memberships if item.student_id == student_id and item.left_at is None), None)
        return record.class_id if record else None

    def set_teacher_assignments(self, class_id: str, assignments: Iterable[TeacherAssignment]) -> list[TeacherAssignment]:
        self.teacher_assignments = [item for item in self.teacher_assignments if item.class_id != class_id] + list(assignments)
        self._persist_lifecycle()
        return [item for item in self.teacher_assignments if item.class_id == class_id]

    def assignments_for_class(self, class_id: str, *, now: datetime | None = None) -> list[TeacherAssignment]:
        return [item for item in self.teacher_assignments if item.class_id == class_id and item.active(now)]

    def teacher_is_assigned(self, class_id: str, teacher_id: str, *, now: datetime | None = None) -> bool:
        managed = [item for item in self.teacher_assignments if item.class_id == class_id]
        return any(item.teacher_id == teacher_id for item in (self.assignments_for_class(class_id, now=now) if managed else [])) or (not managed and teacher_id in self.classrooms[class_id].teachers)

    def _persist(self, classroom: Classroom) -> None:
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("insert into classrooms (class_id, organization_id, state, teachers, schedule) values (?, ?, ?, ?, ?) on conflict(class_id) do update set state=excluded.state, teachers=excluded.teachers, schedule=excluded.schedule", (classroom.class_id, classroom.organization_id, classroom.state.value, json.dumps(sorted(classroom.teachers)), self._serialize_schedule(classroom.schedule)))

    @staticmethod
    def _serialize_schedule(schedule: AccessSchedule | None) -> str | None:
        if schedule is None:
            return None
        return json.dumps({
            "startDate": schedule.start_date.isoformat(),
            "endDate": schedule.end_date.isoformat(),
            "weekdays": sorted(schedule.weekdays),
            "dailyWindows": [{"start": window.start.isoformat(), "end": window.end.isoformat()} for window in schedule.daily_windows],
            "holidayExceptions": sorted(day.isoformat() for day in schedule.holiday_exceptions),
        })

    @staticmethod
    def _deserialize_schedule(value: str | None) -> AccessSchedule | None:
        if not value:
            return None
        from datetime import date, time

        payload = json.loads(value)
        return AccessSchedule(
            start_date=date.fromisoformat(payload["startDate"]),
            end_date=date.fromisoformat(payload["endDate"]),
            weekdays=set(payload["weekdays"]),
            daily_windows=tuple(DailyWindow(time.fromisoformat(window["start"]), time.fromisoformat(window["end"])) for window in payload["dailyWindows"]),
            holiday_exceptions={date.fromisoformat(day) for day in payload.get("holidayExceptions", [])},
        )

    def create(self, class_id: str, organization_id: str) -> Classroom:
        if class_id in self.classrooms:
            raise ValueError("classroom already exists")
        classroom = Classroom(class_id=class_id, organization_id=organization_id)
        self.classrooms[class_id] = classroom
        self._persist(classroom)
        return classroom

    def open(self, class_id: str) -> None:
        classroom = self.classrooms[class_id]
        classroom.state = ClassroomState.OPEN
        self._persist(classroom)
        self.audit_events.append(AuditEvent("classroom.opened", "system", class_id))

    def close(self, class_id: str) -> None:
        classroom = self.classrooms[class_id]
        classroom.state = ClassroomState.CLOSED
        self._persist(classroom)
        self.audit_events.append(AuditEvent("classroom.closed", "system", class_id))

    def assign_teachers(self, class_id: str, teacher_ids: set[str]) -> None:
        classroom = self.classrooms[class_id]
        classroom.teachers = teacher_ids
        self._persist(classroom)

    @property
    def storage_path(self) -> Path | None:
        return self._storage_path

    def refresh_from_storage(self) -> None:
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                rows = connection.execute("select class_id, organization_id, state, teachers, schedule from classrooms").fetchall()
                self._load_lifecycle(connection)
            self.classrooms = {row[0]: Classroom(row[0], row[1], ClassroomState(row[2]), set(json.loads(row[3])), self._deserialize_schedule(row[4])) for row in rows}

    def revoke_teacher_assistance(self, teacher_id: str) -> int:
        keys = [key for key, grant in self.grants.items() if grant.teacher_id == teacher_id]
        for key in keys:
            del self.grants[key]
        return len(keys)

    def set_schedule(self, class_id: str, schedule: AccessSchedule | None) -> None:
        classroom = self.classrooms[class_id]
        classroom.schedule = schedule
        self._persist(classroom)

    def student_creative_access_allowed(self, class_id: str, *, now: datetime | None = None) -> bool:
        classroom = self.classrooms.get(class_id)
        if classroom is None:
            return True
        if classroom.state is not ClassroomState.OPEN:
            return False
        if classroom.schedule is None:
            return True
        current = (now or datetime.now(SHANGHAI)).astimezone(SHANGHAI)
        return is_access_allowed(classroom.schedule, current.isoformat(), class_state=classroom.state)

    def grant_assistance(self, class_id: str, *, teacher_id: str, student_id: str) -> AssistanceGrant:
        classroom = self.classrooms[class_id]
        if classroom.state is not ClassroomState.OPEN or not self.teacher_is_assigned(class_id, teacher_id):
            raise PermissionError("teacher assistance is not allowed")
        grant = AssistanceGrant(class_id=class_id, teacher_id=teacher_id, student_id=student_id)
        self.grants[(class_id, teacher_id, student_id)] = grant
        self.audit_events.append(AuditEvent("assistance.granted", teacher_id, student_id))
        return grant

    def can_act_as(self, class_id: str, teacher_id: str, student_id: str) -> bool:
        classroom = self.classrooms[class_id]
        return classroom.state is ClassroomState.OPEN and (class_id, teacher_id, student_id) in self.grants

    def report_presence(self, class_id: str, student_id: str, *, active_feature: str, task_state: str, lesson_step: int, help_needed: bool) -> StudentPresence:
        classroom = self.classrooms[class_id]
        if classroom.state is ClassroomState.CLOSED:
            raise PermissionError("classroom is closed")
        presence = StudentPresence(student_id, active_feature, task_state, lesson_step, help_needed)
        self.presence[(class_id, student_id)] = presence
        return presence

    def students_for_classroom(self, class_id: str) -> list[StudentPresence]:
        return [presence for (current_class_id, _), presence in self.presence.items() if current_class_id == class_id]

    def classrooms_for_organization(self, organization_id: str) -> list[Classroom]:
        return sorted((item for item in self.classrooms.values() if item.organization_id == organization_id), key=lambda item: item.class_id)


class PostgresAssistanceManager(AssistanceManager):
    """Shared live-classroom state, including temporary teacher assistance."""

    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL classroom manager requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_classrooms (class_id text primary key, organization_id text not null, state text not null, teachers text not null, schedule text)")
            cursor.execute("create table if not exists runtime_assistance_grants (class_id text not null, teacher_id text not null, student_id text not null, primary key (class_id, teacher_id, student_id))")
            cursor.execute("create table if not exists runtime_student_presence (class_id text not null, student_id text not null, active_feature text not null, task_state text not null, lesson_step integer not null, help_needed boolean not null, primary key (class_id, student_id))")
        self._refresh()

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)
    def revoke_teacher_assistance(self, teacher_id: str) -> int:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_assistance_grants where teacher_id = %s", (teacher_id,))
            count = cursor.rowcount
        self._refresh()
        return count
    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select class_id, organization_id, state, teachers, schedule from runtime_classrooms")
            self.classrooms = {str(row[0]): Classroom(str(row[0]), str(row[1]), ClassroomState(row[2]), set(json.loads(row[3])), self._deserialize_schedule(row[4])) for row in cursor.fetchall()}
            cursor.execute("select class_id, teacher_id, student_id from runtime_assistance_grants")
            self.grants = {(str(row[0]), str(row[1]), str(row[2])): AssistanceGrant(str(row[0]), str(row[1]), str(row[2])) for row in cursor.fetchall()}
            cursor.execute("select class_id, student_id, active_feature, task_state, lesson_step, help_needed from runtime_student_presence")
            self.presence = {(str(row[0]), str(row[1])): StudentPresence(str(row[1]), str(row[2]), str(row[3]), int(row[4]), bool(row[5])) for row in cursor.fetchall()}
    def _persist(self, classroom: Classroom) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_classrooms values (%s,%s,%s,%s,%s) on conflict(class_id) do update set state=excluded.state,teachers=excluded.teachers,schedule=excluded.schedule", (classroom.class_id, classroom.organization_id, classroom.state.value, json.dumps(sorted(classroom.teachers)), self._serialize_schedule(classroom.schedule)))
    def create(self, class_id: str, organization_id: str) -> Classroom:
        self._refresh(); return super().create(class_id, organization_id)
    def grant_assistance(self, class_id: str, *, teacher_id: str, student_id: str) -> AssistanceGrant:
        self._refresh(); grant = super().grant_assistance(class_id, teacher_id=teacher_id, student_id=student_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor: cursor.execute("insert into runtime_assistance_grants values (%s,%s,%s) on conflict do nothing", (class_id, teacher_id, student_id))
        return grant
    def can_act_as(self, class_id: str, teacher_id: str, student_id: str) -> bool:
        self._refresh(); return super().can_act_as(class_id, teacher_id, student_id)
    def report_presence(self, class_id: str, student_id: str, *, active_feature: str, task_state: str, lesson_step: int, help_needed: bool) -> StudentPresence:
        self._refresh(); presence = super().report_presence(class_id, student_id, active_feature=active_feature, task_state=task_state, lesson_step=lesson_step, help_needed=help_needed)
        with self._connect_postgres() as connection, connection.cursor() as cursor: cursor.execute("insert into runtime_student_presence values (%s,%s,%s,%s,%s,%s) on conflict(class_id,student_id) do update set active_feature=excluded.active_feature,task_state=excluded.task_state,lesson_step=excluded.lesson_step,help_needed=excluded.help_needed", (class_id, student_id, active_feature, task_state, lesson_step, help_needed))
        return presence
    def students_for_classroom(self, class_id: str) -> list[StudentPresence]: self._refresh(); return super().students_for_classroom(class_id)
    def classrooms_for_organization(self, organization_id: str) -> list[Classroom]: self._refresh(); return super().classrooms_for_organization(organization_id)
