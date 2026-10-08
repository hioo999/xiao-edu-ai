from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Protocol

from packages.agent_runtime.src.dispatcher import AgentExecutionResult
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest

from .versioning import HtmlProject, create_version


class HtmlDispatcher(Protocol):
    def dispatch(self, policy: AgentDispatchRequest, prompt: str, *, organization_id: str) -> AgentExecutionResult: ...


class HtmlWorkspaceService:
    def __init__(self, dispatcher: HtmlDispatcher, storage_path: str | Path | None = None) -> None:
        self._dispatcher = dispatcher
        self._projects: dict[str, HtmlProject] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_storage()
            self._load_storage()

    def _connect(self) -> sqlite3.Connection:
        if not self._storage_path:
            raise RuntimeError("HTML project persistence is not configured")
        connection = sqlite3.connect(self._storage_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("create table if not exists html_projects (project_id text primary key, owner_user_id text not null, current_version_id text)")
            connection.execute("create table if not exists html_versions (version_id text primary key, project_id text not null, title text not null, html text not null, teaching_steps text not null, position integer not null)")

    def _load_storage(self) -> None:
        with self._connect() as connection:
            project_rows = connection.execute("select * from html_projects").fetchall()
            version_rows = connection.execute("select * from html_versions order by project_id, position").fetchall()
        for row in project_rows:
            self._projects[row["project_id"]] = HtmlProject(row["project_id"], row["owner_user_id"], current_version_id=row["current_version_id"])
        for row in version_rows:
            project = self._projects.get(row["project_id"])
            if project is not None:
                from .versioning import HtmlVersion
                project.versions.append(HtmlVersion(row["version_id"], row["title"], row["html"], json.loads(row["teaching_steps"])))

    def _persist(self, project: HtmlProject) -> None:
        if not self._storage_path:
            return
        with self._connect() as connection:
            connection.execute("insert into html_projects values (?, ?, ?) on conflict(project_id) do update set owner_user_id=excluded.owner_user_id, current_version_id=excluded.current_version_id", (project.project_id, project.owner_user_id, project.current_version_id))
            connection.execute("delete from html_versions where project_id = ?", (project.project_id,))
            connection.executemany("insert into html_versions values (?, ?, ?, ?, ?, ?)", [(version.version_id, project.project_id, version.title, version.html, json.dumps(version.teaching_steps, ensure_ascii=False), index) for index, version in enumerate(project.versions)])

    def generate(
        self,
        *,
        project_id: str,
        owner_user_id: str,
        organization_id: str,
        prompt: str,
        policy: AgentDispatchRequest,
    ) -> HtmlProject:
        project = self._projects.setdefault(
            project_id,
            HtmlProject(project_id=project_id, owner_user_id=owner_user_id),
        )
        if project.owner_user_id != owner_user_id:
            raise PermissionError("project owner does not match request owner")
        result = self._dispatcher.dispatch(policy, prompt, organization_id=organization_id)
        create_version(
            project,
            title=prompt[:60] or "未命名网页",
            html=result.html,
            teaching_steps=result.teaching_steps,
        )
        self._persist(project)
        return project

    def get(self, project_id: str, owner_user_id: str) -> HtmlProject:
        project = self._projects.get(project_id)
        if project is None:
            raise LookupError("HTML project not found")
        if project.owner_user_id != owner_user_id:
            raise PermissionError("project owner does not match request owner")
        return project

    def list_for_owner(self, owner_user_id: str) -> list[HtmlProject]:
        return [project for project in self._projects.values() if project.owner_user_id == owner_user_id]

    def restore(self, project_id: str, owner_user_id: str, version_id: str) -> HtmlProject:
        from .versioning import restore_version
        project = self.get(project_id, owner_user_id)
        restore_version(project, version_id)
        self._persist(project)
        return project


class PostgresHtmlWorkspaceService(HtmlWorkspaceService):
    def __init__(self, dispatcher: HtmlDispatcher, database_url: str) -> None:
        super().__init__(dispatcher)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL HTML workspace requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_html_projects (project_id text primary key, owner_user_id text not null, current_version_id text)")
            cursor.execute("create table if not exists runtime_html_versions (version_id text primary key, project_id text not null, title text not null, html text not null, teaching_steps text not null, position integer not null)")
        self._refresh()

    def _connect_postgres(self):
        return self._psycopg.connect(self._database_url)

    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select project_id, owner_user_id, current_version_id from runtime_html_projects")
            projects = cursor.fetchall()
            cursor.execute("select version_id, project_id, title, html, teaching_steps, position from runtime_html_versions order by project_id, position")
            versions = cursor.fetchall()
        self._projects = {str(row[0]): HtmlProject(str(row[0]), str(row[1]), current_version_id=row[2]) for row in projects}
        from .versioning import HtmlVersion
        for row in versions:
            project = self._projects.get(str(row[1]))
            if project is not None:
                project.versions.append(HtmlVersion(str(row[0]), str(row[2]), str(row[3]), json.loads(row[4])))

    def _persist(self, project: HtmlProject) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_html_projects values (%s,%s,%s) on conflict(project_id) do update set owner_user_id=excluded.owner_user_id,current_version_id=excluded.current_version_id", (project.project_id, project.owner_user_id, project.current_version_id))
            cursor.execute("delete from runtime_html_versions where project_id = %s", (project.project_id,))
            for position, version in enumerate(project.versions):
                cursor.execute("insert into runtime_html_versions values (%s,%s,%s,%s,%s,%s)", (version.version_id, project.project_id, version.title, version.html, json.dumps(version.teaching_steps, ensure_ascii=False), position))

    def get(self, project_id: str, owner_user_id: str) -> HtmlProject:
        self._refresh()
        return super().get(project_id, owner_user_id)

    def list_for_owner(self, owner_user_id: str) -> list[HtmlProject]:
        self._refresh()
        return super().list_for_owner(owner_user_id)
