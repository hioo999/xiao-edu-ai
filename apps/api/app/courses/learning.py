from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CourseProgressRecord:
    student_id: str
    course_id: str
    organization_id: str
    percent: int
    completed: bool
    last_block_index: int
    updated_at: str


@dataclass(frozen=True)
class HomeworkSubmission:
    submission_id: str
    student_id: str
    course_id: str
    organization_id: str
    content: str
    status: str
    teacher_feedback: str
    submitted_at: str
    reviewed_at: str


class LearningStore:
    """Student course progress and homework submissions with review feedback."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._progress: dict[tuple[str, str], CourseProgressRecord] = {}
        self._submissions: dict[str, HomeworkSubmission] = {}
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute("create table if not exists course_progress (student_id text not null, course_id text not null, organization_id text not null, percent integer not null, completed integer not null, last_block_index integer not null, updated_at text not null, primary key (student_id, course_id))")
                connection.execute("create table if not exists homework_submissions (submission_id text primary key, student_id text not null, course_id text not null, organization_id text not null, content text not null, status text not null, teacher_feedback text not null, submitted_at text not null, reviewed_at text not null)")
            self._load()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("learning persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _load(self) -> None:
        with self._connect() as connection:
            progress_rows = connection.execute("select student_id, course_id, organization_id, percent, completed, last_block_index, updated_at from course_progress").fetchall()
            submission_rows = connection.execute("select submission_id, student_id, course_id, organization_id, content, status, teacher_feedback, submitted_at, reviewed_at from homework_submissions").fetchall()
        self._progress = {(row["student_id"], row["course_id"]): CourseProgressRecord(row["student_id"], row["course_id"], row["organization_id"], row["percent"], bool(row["completed"]), row["last_block_index"], row["updated_at"]) for row in progress_rows}
        self._submissions = {row["submission_id"]: HomeworkSubmission(row["submission_id"], row["student_id"], row["course_id"], row["organization_id"], row["content"], row["status"], row["teacher_feedback"], row["submitted_at"], row["reviewed_at"]) for row in submission_rows}

    def upsert_progress(self, student_id: str, course_id: str, organization_id: str, percent: int, completed: bool, last_block_index: int) -> CourseProgressRecord:
        record = CourseProgressRecord(student_id, course_id, organization_id, percent, completed, last_block_index, _now())
        self._progress[(student_id, course_id)] = record
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into course_progress values (?, ?, ?, ?, ?, ?, ?) on conflict(student_id, course_id) do update set percent=excluded.percent, completed=excluded.completed, last_block_index=excluded.last_block_index, updated_at=excluded.updated_at", (record.student_id, record.course_id, record.organization_id, record.percent, int(record.completed), record.last_block_index, record.updated_at))
        return record

    def get_progress(self, student_id: str, course_id: str, organization_id: str) -> CourseProgressRecord:
        record = self._progress.get((student_id, course_id))
        if record is None or record.organization_id != organization_id:
            raise KeyError(course_id)
        return record

    def list_progress_for_student(self, student_id: str, organization_id: str) -> list[CourseProgressRecord]:
        return sorted((record for (_student, _course), record in self._progress.items() if _student == student_id and record.organization_id == organization_id), key=lambda item: item.updated_at, reverse=True)

    def list_progress_for_course(self, course_id: str, organization_id: str) -> list[CourseProgressRecord]:
        return sorted((record for (_student, _course), record in self._progress.items() if _course == course_id and record.organization_id == organization_id), key=lambda item: item.updated_at, reverse=True)

    def submit_homework(self, student_id: str, course_id: str, organization_id: str, content: str) -> HomeworkSubmission:
        submission = HomeworkSubmission(f"hw-{uuid.uuid4().hex[:12]}", student_id, course_id, organization_id, content, "submitted", "", _now(), "")
        self._submissions[submission.submission_id] = submission
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert into homework_submissions values (?, ?, ?, ?, ?, ?, ?, ?, ?)", (submission.submission_id, submission.student_id, submission.course_id, submission.organization_id, submission.content, submission.status, submission.teacher_feedback, submission.submitted_at, submission.reviewed_at))
        return submission

    def get_submission(self, submission_id: str, organization_id: str) -> HomeworkSubmission:
        submission = self._submissions.get(submission_id)
        if submission is None or submission.organization_id != organization_id:
            raise KeyError(submission_id)
        return submission

    def list_submissions_for_student(self, student_id: str, organization_id: str) -> list[HomeworkSubmission]:
        return sorted((submission for submission in self._submissions.values() if submission.student_id == student_id and submission.organization_id == organization_id), key=lambda item: item.submitted_at, reverse=True)

    def list_submissions_for_course(self, course_id: str, organization_id: str) -> list[HomeworkSubmission]:
        return sorted((submission for submission in self._submissions.values() if submission.course_id == course_id and submission.organization_id == organization_id), key=lambda item: item.submitted_at, reverse=True)

    def annotate(self, submission_id: str, organization_id: str, feedback: str, status: str = "reviewed") -> HomeworkSubmission:
        submission = self.get_submission(submission_id, organization_id)
        updated = HomeworkSubmission(submission.submission_id, submission.student_id, submission.course_id, submission.organization_id, submission.content, status, feedback, submission.submitted_at, _now())
        self._submissions[submission_id] = updated
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("update homework_submissions set status = ?, teacher_feedback = ?, reviewed_at = ? where submission_id = ?", (updated.status, updated.teacher_feedback, updated.reviewed_at, updated.submission_id))
        return updated


class PostgresLearningStore(LearningStore):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL learning store requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_course_progress (student_id text not null, course_id text not null, organization_id text not null, percent integer not null, completed boolean not null, last_block_index integer not null, updated_at text not null, primary key (student_id, course_id))")
            cursor.execute("create table if not exists runtime_homework_submissions (submission_id text primary key, student_id text not null, course_id text not null, organization_id text not null, content text not null, status text not null, teacher_feedback text not null, submitted_at text not null, reviewed_at text not null)")

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)

    def _progress_from_row(self, row: tuple[object, ...]) -> CourseProgressRecord:
        return CourseProgressRecord(str(row[0]), str(row[1]), str(row[2]), int(row[3]), bool(row[4]), int(row[5]), str(row[6]))

    def _submission_from_row(self, row: tuple[object, ...]) -> HomeworkSubmission:
        return HomeworkSubmission(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[8]))

    def get_progress(self, student_id: str, course_id: str, organization_id: str) -> CourseProgressRecord:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select student_id, course_id, organization_id, percent, completed, last_block_index, updated_at from runtime_course_progress where student_id = %s and course_id = %s and organization_id = %s", (student_id, course_id, organization_id))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(course_id)
        return self._progress_from_row(row)

    def list_progress_for_student(self, student_id: str, organization_id: str) -> list[CourseProgressRecord]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select student_id, course_id, organization_id, percent, completed, last_block_index, updated_at from runtime_course_progress where student_id = %s and organization_id = %s order by updated_at desc", (student_id, organization_id))
            rows = cursor.fetchall()
        return [self._progress_from_row(row) for row in rows]

    def list_progress_for_course(self, course_id: str, organization_id: str) -> list[CourseProgressRecord]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select student_id, course_id, organization_id, percent, completed, last_block_index, updated_at from runtime_course_progress where course_id = %s and organization_id = %s order by updated_at desc", (course_id, organization_id))
            rows = cursor.fetchall()
        return [self._progress_from_row(row) for row in rows]

    def get_submission(self, submission_id: str, organization_id: str) -> HomeworkSubmission:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select submission_id, student_id, course_id, organization_id, content, status, teacher_feedback, submitted_at, reviewed_at from runtime_homework_submissions where submission_id = %s and organization_id = %s", (submission_id, organization_id))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(submission_id)
        return self._submission_from_row(row)

    def list_submissions_for_student(self, student_id: str, organization_id: str) -> list[HomeworkSubmission]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select submission_id, student_id, course_id, organization_id, content, status, teacher_feedback, submitted_at, reviewed_at from runtime_homework_submissions where student_id = %s and organization_id = %s order by submitted_at desc", (student_id, organization_id))
            rows = cursor.fetchall()
        return [self._submission_from_row(row) for row in rows]

    def list_submissions_for_course(self, course_id: str, organization_id: str) -> list[HomeworkSubmission]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select submission_id, student_id, course_id, organization_id, content, status, teacher_feedback, submitted_at, reviewed_at from runtime_homework_submissions where course_id = %s and organization_id = %s order by submitted_at desc", (course_id, organization_id))
            rows = cursor.fetchall()
        return [self._submission_from_row(row) for row in rows]

    def upsert_progress(self, student_id: str, course_id: str, organization_id: str, percent: int, completed: bool, last_block_index: int) -> CourseProgressRecord:
        record = CourseProgressRecord(student_id, course_id, organization_id, percent, completed, last_block_index, _now())
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_course_progress values (%s,%s,%s,%s,%s,%s,%s) on conflict (student_id, course_id) do update set percent=excluded.percent, completed=excluded.completed, last_block_index=excluded.last_block_index, updated_at=excluded.updated_at", (record.student_id, record.course_id, record.organization_id, record.percent, record.completed, record.last_block_index, record.updated_at))
        return record

    def submit_homework(self, student_id: str, course_id: str, organization_id: str, content: str) -> HomeworkSubmission:
        submission = HomeworkSubmission(f"hw-{uuid.uuid4().hex[:12]}", student_id, course_id, organization_id, content, "submitted", "", _now(), "")
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_homework_submissions values (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (submission.submission_id, submission.student_id, submission.course_id, submission.organization_id, submission.content, submission.status, submission.teacher_feedback, submission.submitted_at, submission.reviewed_at))
        return submission

    def annotate(self, submission_id: str, organization_id: str, feedback: str, status: str = "reviewed") -> HomeworkSubmission:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select submission_id, student_id, course_id, organization_id, content, status, teacher_feedback, submitted_at, reviewed_at from runtime_homework_submissions where submission_id = %s and organization_id = %s", (submission_id, organization_id))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(submission_id)
        submission = HomeworkSubmission(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[8]))
        updated = HomeworkSubmission(submission.submission_id, submission.student_id, submission.course_id, submission.organization_id, submission.content, status, feedback, submission.submitted_at, _now())
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("update runtime_homework_submissions set status = %s, teacher_feedback = %s, reviewed_at = %s where submission_id = %s", (updated.status, updated.teacher_feedback, updated.reviewed_at, updated.submission_id))
        return updated


def progress_payload(record: CourseProgressRecord) -> dict[str, object]:
    return {"studentId": record.student_id, "courseId": record.course_id, "percent": record.percent, "completed": record.completed, "lastBlockIndex": record.last_block_index, "updatedAt": record.updated_at}


def submission_payload(submission: HomeworkSubmission) -> dict[str, object]:
    return {"submissionId": submission.submission_id, "studentId": submission.student_id, "courseId": submission.course_id, "content": submission.content, "status": submission.status, "teacherFeedback": submission.teacher_feedback, "submittedAt": submission.submitted_at, "reviewedAt": submission.reviewed_at}
