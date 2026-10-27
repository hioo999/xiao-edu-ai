from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    review_status: str = "draft"
    review_note: str = ""
    lessons: tuple[dict[str, object], ...] = field(default_factory=tuple)


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
            connection.execute("create table if not exists courses (course_id text primary key, organization_id text not null, author_user_id text not null, title text not null, summary text not null, blocks text not null, teacher_script text not null, prompt_examples text not null, student_flow text not null, published integer not null, review_status text not null default 'draft', review_note text not null default '')")
            columns = {row[1] for row in connection.execute("pragma table_info(courses)")}
            if "review_status" not in columns: connection.execute("alter table courses add column review_status text not null default 'draft'")
            if "review_note" not in columns: connection.execute("alter table courses add column review_note text not null default ''")
            if "lessons" not in columns: connection.execute("alter table courses add column lessons text not null default '[]'")
            connection.execute("create table if not exists course_classrooms (course_id text not null, class_id text not null, organization_id text not null, primary key (course_id, class_id))")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("select * from courses").fetchall()
        for row in rows:
            blocks = tuple(LessonBlock(**block) for block in json.loads(row["blocks"]))
            stored_lessons = tuple(json.loads(row["lessons"]))
            if not stored_lessons:
                stored_lessons = tuple({"lessonId": f"{row['course_id']}-lesson-{index + 1}", "title": title, "content": blocks[index].content if index < len(blocks) else title, "sortOrder": index, "required": True} for index, title in enumerate(json.loads(row["student_flow"]) or [block.content for block in blocks]))
            self._courses[row["course_id"]] = CourseRecord(row["course_id"], row["organization_id"], row["author_user_id"], row["title"], row["summary"], blocks, row["teacher_script"], tuple(json.loads(row["prompt_examples"])), tuple(json.loads(row["student_flow"])), bool(row["published"]), row["review_status"], row["review_note"], stored_lessons)

    def _persist(self, course: CourseRecord) -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("insert into courses (course_id, organization_id, author_user_id, title, summary, blocks, teacher_script, prompt_examples, student_flow, published, review_status, review_note, lessons) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict(course_id) do update set title=excluded.title, summary=excluded.summary, blocks=excluded.blocks, teacher_script=excluded.teacher_script, prompt_examples=excluded.prompt_examples, student_flow=excluded.student_flow, published=excluded.published, review_status=excluded.review_status, review_note=excluded.review_note, lessons=excluded.lessons", (course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, json.dumps([block.__dict__ for block in course.blocks], ensure_ascii=False), course.teacher_script, json.dumps(course.prompt_examples, ensure_ascii=False), json.dumps(course.student_flow, ensure_ascii=False), int(course.published), course.review_status, course.review_note, json.dumps(course.lessons, ensure_ascii=False)))

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

    @property
    def storage_path(self) -> Path | None:
        return self._storage_path

    def refresh_from_storage(self) -> None:
        if self._storage_path:
            self._courses.clear()
            self._load_storage()

    def publish_to_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        if not course.published:
            self.save(replace(course, published=True))
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("insert or ignore into course_classrooms values (?, ?, ?)", (course_id, class_id, organization_id))

    def unpublish_from_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        if self._storage_path:
            with self._connect() as connection:
                connection.execute("delete from course_classrooms where course_id = ? and class_id = ? and organization_id = ?", (course_id, class_id, organization_id))
        if course.published and not self._has_class_publication(course_id, organization_id):
            self.save(replace(course, published=False))

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
            cursor.execute("alter table runtime_courses add column if not exists review_status text not null default 'draft'")
            cursor.execute("alter table runtime_courses add column if not exists review_note text not null default ''")
            cursor.execute("alter table runtime_courses add column if not exists lessons text not null default '[]'")
            cursor.execute("create table if not exists runtime_course_classrooms (course_id text not null, class_id text not null, organization_id text not null, primary key (course_id, class_id))")
        self._refresh()

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)

    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select course_id, organization_id, author_user_id, title, summary, blocks, teacher_script, prompt_examples, student_flow, published, review_status, review_note, lessons from runtime_courses")
            rows = cursor.fetchall()
        self._courses = {str(row[0]): CourseRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), tuple(LessonBlock(**block) for block in json.loads(row[5])), str(row[6]), tuple(json.loads(row[7])), tuple(json.loads(row[8])), bool(row[9]), str(row[10]), str(row[11]), tuple(json.loads(row[12]))) for row in rows}

    def _persist(self, course: CourseRecord) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("""insert into runtime_courses (course_id,organization_id,author_user_id,title,summary,blocks,teacher_script,prompt_examples,student_flow,published,review_status,review_note,lessons) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(course_id) do update set title=excluded.title, summary=excluded.summary, blocks=excluded.blocks, teacher_script=excluded.teacher_script, prompt_examples=excluded.prompt_examples, student_flow=excluded.student_flow, published=excluded.published, review_status=excluded.review_status, review_note=excluded.review_note, lessons=excluded.lessons""", (course.course_id, course.organization_id, course.author_user_id, course.title, course.summary, json.dumps([block.__dict__ for block in course.blocks], ensure_ascii=False), course.teacher_script, json.dumps(course.prompt_examples, ensure_ascii=False), json.dumps(course.student_flow, ensure_ascii=False), course.published, course.review_status, course.review_note, json.dumps(course.lessons, ensure_ascii=False)))

    def get(self, course_id: str, organization_id: str) -> CourseRecord:
        self._refresh()
        return super().get(course_id, organization_id)

    def list_for_organization(self, organization_id: str) -> list[CourseRecord]:
        self._refresh()
        return super().list_for_organization(organization_id)

    def publish_to_class(self, course_id: str, class_id: str, organization_id: str) -> None:
        course = self.get(course_id, organization_id)
        if not course.published:
            self.save(replace(course, published=True))
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
            self.save(replace(course, published=False))

    def delete(self, course_id: str, organization_id: str) -> None:
        self.get(course_id, organization_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_courses where course_id = %s", (course_id,))
            cursor.execute("delete from runtime_course_classrooms where course_id = %s", (course_id,))
        self._courses.pop(course_id, None)
