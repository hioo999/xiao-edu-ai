from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock, Lock
import uuid


class StudentAgentWorkspace:
    def __init__(self, path: str | None = None):
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path or ":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        self.session_locks: dict[str, Lock] = {}
        with self.connection:
            self.connection.execute("create table if not exists student_agent_settings (agent_id text primary key, settings text not null)")
            self.connection.execute("create table if not exists student_agent_sessions (session_id text primary key, organization_id text not null, owner_id text not null, agent_id text not null, title text not null, created_at text not null, messages text not null default '[]')")
            columns = {row[1] for row in self.connection.execute("pragma table_info(student_agent_sessions)")}
            if "updated_at" not in columns:
                self.connection.execute("alter table student_agent_sessions add column updated_at text not null default ''")

    def settings(self, agent_id: str) -> dict:
        with self.lock:
            row = self.connection.execute("select settings from student_agent_settings where agent_id=?", (agent_id,)).fetchone()
        return json.loads(row[0]) if row else {"capability": "text", "skillIds": [], "mcpIds": [], "knowledgeIds": [], "runtime": "gateway"}

    def save_settings(self, agent_id: str, settings: dict) -> dict:
        with self.lock, self.connection:
            self.connection.execute("insert into student_agent_settings values (?,?) on conflict(agent_id) do update set settings=excluded.settings", (agent_id, json.dumps(settings, ensure_ascii=False)))
        return settings

    def list_sessions(self, organization_id: str, owner_id: str, agent_id: str) -> list[dict]:
        with self.lock:
            rows = self.connection.execute("select * from student_agent_sessions where organization_id=? and owner_id=? and agent_id=? order by case when updated_at='' then created_at else updated_at end desc", (organization_id, owner_id, agent_id)).fetchall()
        return [self.payload(row) for row in rows]

    @staticmethod
    def payload(row) -> dict:
        return {"sessionId": row["session_id"], "agentId": row["agent_id"], "title": row["title"], "createdAt": row["created_at"], "messages": json.loads(row["messages"])}

    def create(self, organization_id: str, owner_id: str, agent_id: str, title: str) -> dict:
        session_id = f"chat-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self.connection:
            self.connection.execute("insert into student_agent_sessions (session_id,organization_id,owner_id,agent_id,title,created_at,messages,updated_at) values (?,?,?,?,?,?,?,?)", (session_id, organization_id, owner_id, agent_id, title[:80], now, "[]", now))
        return self.get(session_id, organization_id, owner_id)

    def get(self, session_id: str, organization_id: str, owner_id: str) -> dict:
        with self.lock:
            row = self.connection.execute("select * from student_agent_sessions where session_id=? and organization_id=? and owner_id=?", (session_id, organization_id, owner_id)).fetchone()
        if row is None:
            raise KeyError("conversation not found")
        return self.payload(row)

    def append(self, session_id: str, organization_id: str, owner_id: str, question: str, answer: dict) -> dict:
        with self.lock, self.connection:
            current = self.get(session_id, organization_id, owner_id)
            messages = [*current["messages"], {"role": "student", "text": question}, {"role": "assistant", **answer}]
            self.connection.execute("update student_agent_sessions set messages=?,title=?,updated_at=? where session_id=?", (json.dumps(messages, ensure_ascii=False), question[:40] if not current["messages"] else current["title"], datetime.now(timezone.utc).isoformat(), session_id))
        return self.get(session_id, organization_id, owner_id)

    @contextmanager
    def conversation_lock(self, session_id: str):
        with self.lock:
            guard = self.session_locks.setdefault(session_id, Lock())
        if not guard.acquire(blocking=False):
            raise BlockingIOError("这个对话正在生成，请稍后再发送。")
        try:
            yield
        finally:
            guard.release()
