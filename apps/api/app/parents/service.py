from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import uuid
from datetime import datetime, timezone

@dataclass(frozen=True)
class ParentAccount:
    parent_id: str
    organization_id: str
    name: str
    mobile_masked: str
    status: str = "active"

class ParentPortalStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.path = Path(storage_path) if storage_path else None
        self.accounts: dict[str, ParentAccount] = {}
        self.relations: dict[tuple[str, str], dict] = {}
        self.visibility: dict[tuple[str, str], dict] = {}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True); self._init(); self._load()
    def _connect(self):
        if not self.path: raise RuntimeError("parent storage is not configured")
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._connect() as c:
            c.execute("create table if not exists parent_accounts (parent_id text primary key, organization_id text not null, name text not null, mobile_masked text not null, status text not null default 'active')")
            c.execute("create table if not exists parent_student_relations (parent_id text not null, student_id text not null, relationship text not null, status text not null, verified_by text, verified_at text, primary key(parent_id, student_id))")
            c.execute("create table if not exists parent_visibility (resource_type text not null, resource_id text not null, visible integer not null, published_by text, published_at text, revoked_at text, primary key(resource_type, resource_id))")
            c.execute("create table if not exists parent_feedback (id text primary key, organization_id text not null, teacher_id text not null, student_id text not null, course_id text, work_id text, title text not null, content text not null, status text not null, created_at text not null)")
            c.execute("create table if not exists parent_notifications (id text primary key, organization_id text not null, student_id text, title text not null, content text not null, read_at text, created_at text not null)")
    def _load(self):
        with self._connect() as c:
            self.accounts={r['parent_id']:ParentAccount(r['parent_id'],r['organization_id'],r['name'],r['mobile_masked'],r['status']) for r in c.execute('select * from parent_accounts')}
            self.relations={(r['parent_id'],r['student_id']):dict(r) for r in c.execute('select * from parent_student_relations')}
            self.visibility={(r['resource_type'],r['resource_id']):dict(r) for r in c.execute('select * from parent_visibility')}
    def create_parent(self, org: str, name: str, mobile_masked: str) -> ParentAccount:
        p=ParentAccount(str(uuid.uuid4()),org,name,mobile_masked); self.accounts[p.parent_id]=p
        if self.path:
            with self._connect() as c: c.execute('insert into parent_accounts values (?,?,?,?,?)',(p.parent_id,p.organization_id,p.name,p.mobile_masked,p.status))
        return p
    def bind(self, parent_id: str, student_id: str, relationship: str, actor: str, status: str='verified') -> dict:
        row={'parent_id':parent_id,'student_id':student_id,'relationship':relationship,'status':status,'verified_by':actor,'verified_at':datetime.now(timezone.utc).isoformat()}; self.relations[(parent_id,student_id)]=row
        if self.path:
            with self._connect() as c: c.execute('insert or replace into parent_student_relations values (?,?,?,?,?,?)',tuple(row.values()))
        return row
    def students(self,parent_id:str)->list[str]: return [s for (p,s),r in self.relations.items() if p==parent_id and r['status']=='verified']
    def set_visibility(self, resource_type:str, resource_id:str, visible:bool, actor:str):
        row={'resource_type':resource_type,'resource_id':resource_id,'visible':int(visible),'published_by':actor,'published_at':datetime.now(timezone.utc).isoformat() if visible else None,'revoked_at':None if visible else datetime.now(timezone.utc).isoformat()}; self.visibility[(resource_type,resource_id)]=row
        if self.path:
            with self._connect() as c: c.execute('insert or replace into parent_visibility values (?,?,?,?,?,?)',tuple(row.values()))
        return row
    def is_visible(self, typ:str, rid:str)->bool: return bool(self.visibility.get((typ,rid),{}).get("visible",0))
    def add_feedback(self, org, teacher, student, title, content, course_id=None, work_id=None):
        row={"id":f"feedback-{uuid.uuid4().hex[:12]}","organization_id":org,"teacher_id":teacher,"student_id":student,"course_id":course_id,"work_id":work_id,"title":title,"content":content,"status":"published","created_at":datetime.now(timezone.utc).isoformat()}
        if self.path:
            with self._connect() as c: c.execute("insert into parent_feedback values (?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
        return row
    def feedback_for_student(self, org, student):
        if not self.path: return []
        with self._connect() as c: return [dict(r) for r in c.execute("select * from parent_feedback where organization_id=? and student_id=? and status=\'published\' order by created_at desc",(org,student))]
    def add_notification(self, org, student, title, content):
        row={"id":f"notice-{uuid.uuid4().hex[:12]}","organization_id":org,"student_id":student,"title":title,"content":content,"read_at":None,"created_at":datetime.now(timezone.utc).isoformat()}
        if self.path:
            with self._connect() as c: c.execute("insert into parent_notifications values (?,?,?,?,?,?,?)", tuple(row.values()))
        return row
    def notifications_for_student(self, org, student):
        if not self.path: return []
        with self._connect() as c: return [dict(r) for r in c.execute("select * from parent_notifications where organization_id=? and (student_id=? or student_id is null) order by created_at desc",(org,student))]
