from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class LearningEvent:
    student_id: str
    event_type: str
    label: str


class ReportService:
    def __init__(self, events: list[LearningEvent] | None = None, storage_path: str | Path | None = None) -> None:
        self._events = events or []
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("create table if not exists learning_events (student_id text not null, event_type text not null, label text not null)")
                self._events = [LearningEvent(*row) for row in connection.execute("select student_id, event_type, label from learning_events")]

    def record(self, event: LearningEvent) -> None:
        self._events.append(event)
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("insert into learning_events values (?, ?, ?)", (event.student_id, event.event_type, event.label))

    def for_student(self, student_id: str) -> dict[str, object]:
        owned = [event for event in self._events if event.student_id == student_id]
        if not owned:
            raise PermissionError("student report is not available")
        return {
            "studentId": student_id,
            "completedLessons": [event.label for event in owned if event.event_type == "lesson.completed"],
            "submittedAssignments": [event.label for event in owned if event.event_type == "homework.submitted"],
            "reviewedAssignments": [event.label for event in owned if event.event_type == "homework.reviewed"],
            "aiGenerated": True,
        }


class PostgresReportService(ReportService):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL report service requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_learning_events (student_id text not null, event_type text not null, label text not null)")
            cursor.execute("create index if not exists runtime_learning_events_student_idx on runtime_learning_events (student_id)")

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)
    def record(self, event: LearningEvent) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_learning_events values (%s, %s, %s)", (event.student_id, event.event_type, event.label))
    def for_student(self, student_id: str) -> dict[str, object]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select student_id, event_type, label from runtime_learning_events where student_id = %s", (student_id,))
            events = [LearningEvent(*row) for row in cursor.fetchall()]
        if not events:
            raise PermissionError("student report is not available")
        return {"studentId": student_id, "completedLessons": [event.label for event in events if event.event_type == "lesson.completed"], "submittedAssignments": [event.label for event in events if event.event_type == "homework.submitted"], "reviewedAssignments": [event.label for event in events if event.event_type == "homework.reviewed"], "aiGenerated": True}
