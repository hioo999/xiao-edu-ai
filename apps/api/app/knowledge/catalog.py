from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import uuid

from .scopes import KnowledgeDocument, KnowledgeScope


class KnowledgeCatalog:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._docs: dict[str, KnowledgeDocument] = {}
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("create table if not exists knowledge_documents (document_id text primary key, scope text not null, scope_id text not null, title text not null, organization_id text, content text not null default '')")
                columns = {row[1] for row in connection.execute("pragma table_info(knowledge_documents)")}
                if "organization_id" not in columns:
                    connection.execute("alter table knowledge_documents add column organization_id text")
                if "content" not in columns:
                    connection.execute("alter table knowledge_documents add column content text not null default ''")
                self._docs = {row[0]: KnowledgeDocument(row[0], KnowledgeScope(row[1]), row[2], row[3], row[4], row[5]) for row in connection.execute("select document_id, scope, scope_id, title, organization_id, content from knowledge_documents")}

    def add(self, scope: KnowledgeScope, scope_id: str, title: str, organization_id: str | None = None, content: str = "") -> KnowledgeDocument:
        document = KnowledgeDocument(f"doc-{uuid.uuid4().hex[:12]}", scope, scope_id, title, organization_id, content)
        self._docs[document.document_id] = document
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("insert into knowledge_documents values (?, ?, ?, ?, ?, ?)", (document.document_id, document.scope.value, document.scope_id, document.title, document.organization_id, document.content))
        return document

    def list(self, organization_id: str) -> list[KnowledgeDocument]:
        return [document for document in self._docs.values() if document.scope is KnowledgeScope.PLATFORM or document.organization_id in (None, organization_id)]

    def search(self, organization_id: str, query: str, *, course_id: str | None = None) -> list[KnowledgeDocument]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        visible = self.list(organization_id)
        terms = {normalized}
        terms.update(token for token in re.findall(r"[a-z0-9]{2,}", normalized) if token)
        terms.update(normalized[index:index + 2] for index in range(len(normalized) - 1) if normalized[index:index + 2].strip())
        scoped = []
        for document in visible:
            if document.scope is KnowledgeScope.COURSE and document.scope_id != course_id:
                continue
            haystack = f"{document.title}\n{document.content}".lower()
            if any(term in haystack for term in terms):
                scoped.append(document)
        return scoped

    def delete(self, document_id: str, organization_id: str, *, platform_admin: bool) -> None:
        document = self._docs.get(document_id)
        if document is None:
            raise KeyError(document_id)
        if document.scope is KnowledgeScope.PLATFORM:
            if not platform_admin:
                raise PermissionError(document_id)
        elif document.organization_id not in (None, organization_id):
            raise PermissionError(document_id)
        del self._docs[document_id]
        if self._storage_path:
            with sqlite3.connect(self._storage_path) as connection:
                connection.execute("delete from knowledge_documents where document_id = ?", (document_id,))


class PostgresKnowledgeCatalog(KnowledgeCatalog):
    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL knowledge catalog requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_knowledge_documents (document_id text primary key, scope text not null, scope_id text not null, title text not null, organization_id text, content text not null default '')")
        self._refresh()

    def _connect_postgres(self): return self._psycopg.connect(self._database_url)

    def _refresh(self) -> None:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select document_id, scope, scope_id, title, organization_id, content from runtime_knowledge_documents")
            rows = cursor.fetchall()
        self._docs = {str(row[0]): KnowledgeDocument(str(row[0]), KnowledgeScope(row[1]), str(row[2]), str(row[3]), row[4], str(row[5])) for row in rows}

    def add(self, scope: KnowledgeScope, scope_id: str, title: str, organization_id: str | None = None, content: str = "") -> KnowledgeDocument:
        document = KnowledgeDocument(f"doc-{uuid.uuid4().hex[:12]}", scope, scope_id, title, organization_id, content)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_knowledge_documents values (%s, %s, %s, %s, %s, %s)", (document.document_id, document.scope.value, document.scope_id, document.title, document.organization_id, document.content))
        self._docs[document.document_id] = document
        return document

    def list(self, organization_id: str) -> list[KnowledgeDocument]:
        self._refresh()
        return super().list(organization_id)

    def delete(self, document_id: str, organization_id: str, *, platform_admin: bool) -> None:
        self._refresh()
        super().delete(document_id, organization_id, platform_admin=platform_admin)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_knowledge_documents where document_id = %s", (document_id,))
