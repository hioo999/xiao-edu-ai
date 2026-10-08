from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3

from .exporter import LessonBlock


@dataclass(frozen=True)
class CourseRecord:
    course_id: str
    organization_id: str
    author_user_id: str
    title: str
    summary: str
    blocks: tuple[LessonBlock, ...] = field(default_factory=tuple)
    teacher_script: str = ""
    prompt_examples: tuple[str, ...] = field(default_factory=tuple)
    student_flow: tuple[str, ...] = field(default_factory=tuple)
    published: bool = False


class CourseCatalog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._courses: dict[str, CourseRecord] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("course persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("create table if not exists courses (course_id text primary key, organization_id text not null, author_user_id text not null, title text not null, summary text not null, blocks text not null, teacher_script text not null, prompt_examples text not null, student_flow text not null, published integer not null)")
            connection.execute("create table if not exists course_classrooms (course_id text not null, class_id text not null, organization_id text not null, primary key (course_id, class_id))")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select * from courses").fetchall()
        for row in rows:
            blocks = tuple(LessonBlock(**block) for block in json.loads(row["blocks"]))
            self._courses[row["course_id"]] = CourseRecord(row["course_id"], row["organization_id"], row["author_user_id"], row["title"], row["summary"], blocks, row["teacher_script"], tuple(json.loads(row["prompt_examples"])), tuple(json.loads(row["student_flow"])), bool(row["published"]))

    def _persist(self, course: CourseRecord) -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("insert into courses values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict(course_id) do update set title=excluded.title, summary=excluded.summary, blocks=excluded.blocks, teacher_script=excluded.teacher_script, prompt_examples=excluded.prompt_examples, student_flow=excluded.student_flow, published=excluded.published", (course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, json.dumps([block.__dict__ for block in course.blocks], ensure_ascii=False), course.teacher_script, json.dumps(course.prompt_examples, ensure_ascii=False), json.dumps(course.student_flow, ensure_ascii=False), int(course.published)))

    def save(self, course: CourseRecord) -> CourseRecord:
        existing = self._courses.get(course.course_id)
        if existing is not None and existing.organization_id != course.organization_id:
            raise PermissionError("course belongs to another organization")
        self._courses[course.course_id] = course
        self._persist(course)
        return course

    def get(self, course_id: str, organization_id: str) -> CourseRecord:
        course = self._courses.get(course_id)
        if course is None:
            raise KeyError(course_id)
        if course.organization_id != organization_id:
            raise PermissionError("course belongs to another organization")
        return course

    def list_for_organization(self, organization_id: str) -> list[CourseRecord]:
        return [course for course in self._courses.values() if course.organization_id == organization_id]

    def publish_to_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        if not course.published:
            self.save(CourseRecord(course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, course.blocks, course.teacher_script, course.prompt_examples, course.student_flow, True))
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert or ignore into course_classrooms values (?, ?, ?)", (course_id, class_id, organization_id))

    def unpublish_from_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from course_classrooms where course_id = ? and class_id = ? and organization_id = ?", (course_id, class_id, organization_id))
        if course.published and not self._has_class_publication(course_id, organization_id):
            self.save(CourseRecord(course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, course.blocks, course.teacher_script, course.prompt_examples, course.student_flow, False))

    def _has_class_publication(self, course_id: str, organization_id: str) -> bool:
        if not self._storage_path:
            return False
        with self._connect() as connection:
            return connection.execute("select 1 from course_classrooms where course_id = ? and organization_id = ? limit 1", (course_id, organization_id)).fetchone() is not None

    def delete(self, course_id: str, organization_id: str) -> None:
        self.get(course_id, organization_id)
        del self._courses[course_id]
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from courses where course_id = ?", (course_id,))
                connection.execute("delete from course_classrooms where course_id = ?", (course_id,))

    def list_for_class(self, class_id: str, organization_id: str) -> list[CourseRecord]:
        if not self._storage_path:
            return []
        with self._connect() as connection:
            rows = connection.execute("select course_id from course_classrooms where class_id = ? and organization_id = ?", (class_id, organization_id)).fetchall()
        return [self._courses[row[0]] for row in rows if row[0] in self._courses and self._courses[row[0]].published]


class PostgresCourseCatalog(CourseCatalog):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL course catalog requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""create table if not exists runtime_courses (course_id text primary key, organization_id text not null, author_user_id text not null, title text not null, summary text not null, blocks text not null, teacher_script text not null, prompt_examples text not null, student_flow text not null, published boolean not null)""")
            cursor.execute("create table if not exists runtime_course_classrooms (course_id text not null, class_id text not null, organization_id text not null, primary key (course_id, class_id))")
        self._refresh()

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)

    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select course_id, organization_id, author_user_id, title, summary, blocks, teacher_script, prompt_examples, student_flow, published from runtime_courses")
            rows = cursor.fetchall()
        self._courses = {str(row[0]): CourseRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), tuple(LessonBlock(**block) for block in json.loads(row[5])), str(row[6]), tuple(json.loads(row[7])), tuple(json.loads(row[8])), bool(row[9])) for row in rows}

    def _persist(self, course: CourseRecord) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into runtime_courses values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(course_id) do update set title=excluded.title, summary=excluded.summary, blocks=excluded.blocks, teacher_script=excluded.teacher_script, prompt_examples=excluded.prompt_examples, student_flow=excluded.student_flow, published=excluded.published""", (course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, json.dumps([block.__dict__ for block in course.blocks], ensure_ascii=False), course.teacher_script, json.dumps(course.prompt_examples, ensure_ascii=False), json.dumps(course.student_flow, ensure_ascii=False), course.published))

    def get(self, course_id: str, organization_id: str) -> CourseRecord:
        self._refresh()
        return super().get(course_id, organization_id)

    def list_for_organization(self, organization_id: str) -> list[CourseRecord]:
        self._refresh()
        return super().list_for_organization(organization_id)

    def publish_to_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        if not course.published:
            self.save(CourseRecord(course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, course.blocks, course.teacher_script, course.prompt_examples, course.student_flow, True))
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_course_classrooms values (%s, %s, %s) on conflict do nothing", (course_id, class_id, organization_id))

    def list_for_class(self, class_id: str, organization_id: str) -> list[CourseRecord]:
        self._refresh()
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select course_id from runtime_course_classrooms where class_id = %s and organization_id = %s", (class_id, organization_id))
            ids = [row[0] for row in cursor.fetchall()]
        return [self._courses[course_id] for course_id in ids if course_id in self._courses and self._courses[course_id].published]

    def unpublish_from_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_course_classrooms where course_id = %s and class_id = %s and organization_id = %s", (course_id, class_id, organization_id))
            cursor.execute("select 1 from runtime_course_classrooms where course_id = %s and organization_id = %s limit 1", (course_id, organization_id))
            has_publication = cursor.fetchone() is not None
        if course.published and not has_publication:
            self.save(CourseRecord(course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, course.blocks, course.teacher_script, course.prompt_examples, course.student_flow, False))

    def delete(self, course_id: str, organization_id: str) -> None:
        self.get(course_id, organization_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_courses where course_id = %s", (course_id,))
            cursor.execute("delete from runtime_course_classrooms where course_id = %s", (course_id,))
        self._courses.pop(course_id, None)
