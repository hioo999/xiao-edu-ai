from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class ManagedTool:
    tool_id: str
    kind: str
    name: str
    capabilities: str
    enabled: bool
    organization_id: str | None = None
    instruction: str = ""


@dataclass(frozen=True)
class ManagedAgent:
    agent_id: str
    name: str
    capability: str
    grade_range: str
    published: bool
    organization_id: str | None = None


@dataclass(frozen=True)
class StudentAgent:
    agent_id: str
    organization_id: str
    owner_user_id: str
    name: str
    description: str
    category: str
    instructions: str
    provider_id: str


class AgentCatalog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._tools: dict[str, ManagedTool] = {}
        self._agents: dict[str, ManagedAgent] = {}
        self._student_agents: dict[str, StudentAgent] = {}
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute(
                    "create table if not exists managed_tools (tool_id text primary key, kind text not null, name text not null, capabilities text not null, enabled integer not null, organization_id text, instruction text not null default '')"
                )
                connection.execute(
                    "create table if not exists managed_agents (agent_id text primary key, name text not null, capability text not null, grade_range text not null, published integer not null, organization_id text)"
                )
                connection.execute("create table if not exists student_agents (agent_id text primary key, organization_id text not null, owner_user_id text not null, name text not null, description text not null, category text not null, instructions text not null, provider_id text not null)")
                tool_columns = {row[1] for row in connection.execute("pragma table_info(managed_tools)")}
                agent_columns = {row[1] for row in connection.execute("pragma table_info(managed_agents)")}
                if "organization_id" not in tool_columns:
                    connection.execute("alter table managed_tools add column organization_id text")
                if "instruction" not in tool_columns:
                    connection.execute("alter table managed_tools add column instruction text not null default ''")
                if "organization_id" not in agent_columns:
                    connection.execute("alter table managed_agents add column organization_id text")
                self._tools = {
                    row[0]: ManagedTool(row[0], row[1], row[2], row[3], bool(row[4]), row[5], row[6])
                    for row in connection.execute("select tool_id, kind, name, capabilities, enabled, organization_id, instruction from managed_tools")
                }
                self._agents = {
                    row[0]: ManagedAgent(row[0], row[1], row[2], row[3], bool(row[4]), row[5])
                    for row in connection.execute("select agent_id, name, capability, grade_range, published, organization_id from managed_agents")
                }
                self._student_agents = {
                    row[0]: StudentAgent(*row)
                    for row in connection.execute("select agent_id, organization_id, owner_user_id, name, description, category, instructions, provider_id from student_agents")
                }

    def list_student_agents(self, organization_id: str, owner_user_id: str) -> list[StudentAgent]:
        return sorted((agent for agent in self._student_agents.values() if agent.organization_id == organization_id and agent.owner_user_id == owner_user_id), key=lambda agent: agent.name)

    def save_student_agent(self, agent: StudentAgent) -> StudentAgent:
        self._student_agents[agent.agent_id] = agent
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("insert into student_agents values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(agent_id) do update set name=excluded.name, description=excluded.description, category=excluded.category, instructions=excluded.instructions, provider_id=excluded.provider_id", (agent.agent_id, agent.organization_id, agent.owner_user_id, agent.name, agent.description, agent.category, agent.instructions, agent.provider_id))
        return agent

    def delete_student_agent(self, agent_id: str, organization_id: str, owner_user_id: str) -> None:
        agent = self._student_agents.get(agent_id)
        if agent is None or agent.organization_id != organization_id or agent.owner_user_id != owner_user_id:
            raise KeyError(agent_id)
        del self._student_agents[agent_id]
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("delete from student_agents where agent_id = ? and organization_id = ? and owner_user_id = ?", (agent_id, organization_id, owner_user_id))

    def save(self, tool: ManagedTool) -> ManagedTool:
        self._tools[tool.tool_id] = tool
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute(
                    "insert into managed_tools (tool_id, kind, name, capabilities, enabled, organization_id, instruction) values (?, ?, ?, ?, ?, ?, ?) on conflict(tool_id) do update set kind=excluded.kind, name=excluded.name, capabilities=excluded.capabilities, enabled=excluded.enabled, organization_id=excluded.organization_id, instruction=excluded.instruction",
                    (tool.tool_id, tool.kind, tool.name, tool.capabilities, int(tool.enabled), tool.organization_id, tool.instruction),
                )
        return tool

    def list(self, kind: str, organization_id: str | None = None) -> list[ManagedTool]:
        return sorted((tool for tool in self._tools.values() if tool.kind == kind and tool.organization_id in (None, organization_id)), key=lambda tool: tool.name)

    def delete(self, kind: str, tool_id: str) -> None:
        tool = self._tools.get(tool_id)
        if tool is None or tool.kind != kind:
            raise KeyError(tool_id)
        del self._tools[tool_id]
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("delete from managed_tools where tool_id = ?", (tool_id,))

    def save_agent(self, agent: ManagedAgent) -> ManagedAgent:
        self._agents[agent.agent_id] = agent
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute(
                    "insert into managed_agents (agent_id, name, capability, grade_range, published, organization_id) values (?, ?, ?, ?, ?, ?) on conflict(agent_id) do update set name=excluded.name, capability=excluded.capability, grade_range=excluded.grade_range, published=excluded.published, organization_id=excluded.organization_id",
                    (agent.agent_id, agent.name, agent.capability, agent.grade_range, int(agent.published), agent.organization_id),
                )
        return agent

    def list_agents(self, organization_id: str | None = None) -> list[ManagedAgent]:
        return sorted((agent for agent in self._agents.values() if agent.organization_id in (None, organization_id)), key=lambda agent: agent.name)

    def delete_agent(self, agent_id: str) -> None:
        if agent_id not in self._agents:
            raise KeyError(agent_id)
        del self._agents[agent_id]
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("delete from managed_agents where agent_id = ?", (agent_id,))


class PostgresAgentCatalog(AgentCatalog):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL agent catalog requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_managed_tools (tool_id text primary key, kind text not null, name text not null, capabilities text not null, enabled boolean not null, organization_id text, instruction text not null default '')")
            cursor.execute("alter table runtime_managed_tools add column if not exists instruction text not null default ''")
            cursor.execute("create table if not exists runtime_managed_agents (agent_id text primary key, name text not null, capability text not null, grade_range text not null, published boolean not null, organization_id text)")
            cursor.execute("create table if not exists runtime_student_agents (agent_id text primary key, organization_id text not null, owner_user_id text not null, name text not null, description text not null, category text not null, instructions text not null, provider_id text not null)")
        self._refresh()

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)
    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select tool_id, kind, name, capabilities, enabled, organization_id, instruction from runtime_managed_tools")
            self._tools = {str(row[0]): ManagedTool(str(row[0]), str(row[1]), str(row[2]), str(row[3]), bool(row[4]), row[5], str(row[6])) for row in cursor.fetchall()}
            cursor.execute("select agent_id, name, capability, grade_range, published, organization_id from runtime_managed_agents")
            self._agents = {str(row[0]): ManagedAgent(str(row[0]), str(row[1]), str(row[2]), str(row[3]), bool(row[4]), row[5]) for row in cursor.fetchall()}
            cursor.execute("select agent_id, organization_id, owner_user_id, name, description, category, instructions, provider_id from runtime_student_agents")
            self._student_agents = {str(row[0]): StudentAgent(*row) for row in cursor.fetchall()}
    def save(self, tool: ManagedTool) -> ManagedTool:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_managed_tools (tool_id, kind, name, capabilities, enabled, organization_id, instruction) values (%s,%s,%s,%s,%s,%s,%s) on conflict(tool_id) do update set kind=excluded.kind,name=excluded.name,capabilities=excluded.capabilities,enabled=excluded.enabled,organization_id=excluded.organization_id,instruction=excluded.instruction", (tool.tool_id, tool.kind, tool.name, tool.capabilities, tool.enabled, tool.organization_id, tool.instruction))
        self._tools[tool.tool_id] = tool; return tool
    def list(self, kind: str, organization_id: str | None = None) -> list[ManagedTool]: self._refresh(); return super().list(kind, organization_id)
    def delete(self, kind: str, tool_id: str) -> None:
        self._refresh(); super().delete(kind, tool_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor: cursor.execute("delete from runtime_managed_tools where tool_id = %s", (tool_id,))
    def save_agent(self, agent: ManagedAgent) -> ManagedAgent:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_managed_agents values (%s,%s,%s,%s,%s,%s) on conflict(agent_id) do update set name=excluded.name,capability=excluded.capability,grade_range=excluded.grade_range,published=excluded.published,organization_id=excluded.organization_id", (agent.agent_id, agent.name, agent.capability, agent.grade_range, agent.published, agent.organization_id))
        self._agents[agent.agent_id] = agent; return agent
    def list_agents(self, organization_id: str | None = None) -> list[ManagedAgent]: self._refresh(); return super().list_agents(organization_id)
    def delete_agent(self, agent_id: str) -> None:
        self._refresh(); super().delete_agent(agent_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor: cursor.execute("delete from runtime_managed_agents where agent_id = %s", (agent_id,))
    def list_student_agents(self, organization_id: str, owner_user_id: str) -> list[StudentAgent]:
        self._refresh()
        return super().list_student_agents(organization_id, owner_user_id)
    def save_student_agent(self, agent: StudentAgent) -> StudentAgent:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_student_agents values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict(agent_id) do update set name=excluded.name,description=excluded.description,category=excluded.category,instructions=excluded.instructions,provider_id=excluded.provider_id", (agent.agent_id, agent.organization_id, agent.owner_user_id, agent.name, agent.description, agent.category, agent.instructions, agent.provider_id))
        return agent
    def delete_student_agent(self, agent_id: str, organization_id: str, owner_user_id: str) -> None:
        self._refresh()
        super().delete_student_agent(agent_id, organization_id, owner_user_id)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_student_agents where agent_id = %s and organization_id = %s and owner_user_id = %s", (agent_id, organization_id, owner_user_id))
