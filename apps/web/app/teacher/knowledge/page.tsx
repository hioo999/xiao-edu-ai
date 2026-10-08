"use client";

import { FormEvent, useEffect, useState } from "react";

import { addKnowledge, currentSession, deleteKnowledge, KnowledgeDocument, listKnowledge } from "../../../src/api-client";

export default function TeacherKnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("");

  async function refresh() {
    const session = currentSession();
    if (session) setDocuments(await listKnowledge(session.accessToken));
  }

  useEffect(() => { void refresh().catch(() => setStatus("暂时无法读取知识库。")); }, []);

  async function add(event: FormEvent) {
    event.preventDefault();
    const session = currentSession();
    if (!session || !title.trim()) return setStatus("请填写知识条目标题。");
    try {
      await addKnowledge(session.accessToken, title.trim());
      setTitle("");
      setStatus("知识条目已保存。");
      await refresh();
    } catch {
      setStatus("保存知识条目失败。");
    }
  }

  async function remove(item: KnowledgeDocument) {
    const session = currentSession();
    if (!session || !window.confirm(`确定删除“${item.title}”吗？`)) return;
    try {
      await deleteKnowledge(session.accessToken, item.document_id);
      await refresh();
      setStatus("知识条目已删除。");
    } catch {
      setStatus("删除失败。");
    }
  }

  return (
    <main className="teacher-shell">
      <header className="teacher-home-header"><div><p className="student-home__eyebrow">KNOWLEDGE BASE</p><h1>知识库</h1><p>把教学规范、课程资料整理成智能体可以引用的知识条目。</p></div></header>
      <section className="section-workspace">
        <form className="settings-form" onSubmit={add}>
          <label>知识条目标题<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：小学网页创作教学规范" /></label>
          <button className="teacher-primary-link" type="submit">保存知识条目</button>
        </form>
        {status && <div className="settings-note">{status}</div>}
        <div className="backoffice-table">
          <div><span>标题</span><span>范围</span><span>范围 ID</span><span>操作</span></div>
          {documents.map((item) => <div key={item.document_id}><strong>{item.title}</strong><span>{item.scope}</span><span>{item.scope_id}</span><span><button onClick={() => void remove(item)}>删除</button></span></div>)}
          {documents.length === 0 && <div><span>暂无知识条目</span><span>—</span><span>—</span><span>—</span></div>}
        </div>
      </section>
    </main>
  );
}
