"use client";

import { useEffect, useState } from "react";

import { batchReviewWorks, CreativeWork, currentSession, listReviewWorks } from "../../../src/api-client";

export default function TeacherReviewPage() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    const session = currentSession();
    if (!session) return;
    try {
      setWorks(await listReviewWorks(session.accessToken, {}));
    } catch {
      setStatus("无法读取作品审核列表。");
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function review(state: "approved" | "rejected", featured: boolean) {
    const session = currentSession();
    if (!session || !selected.length) return setStatus("请先勾选作品。");
    try {
      await batchReviewWorks(session.accessToken, selected, state, featured);
      setStatus(`已处理 ${selected.length} 个作品。`);
      setSelected([]);
      await refresh();
    } catch {
      setStatus("批量审核失败。");
    }
  }

  return (
    <main className="teacher-shell">
      <header className="teacher-home-header"><div><p className="student-home__eyebrow">WORK REVIEW</p><h1>作品审核</h1><p>审核学生作品，通过后进入作品墙，供其他同学学习和点赞。</p></div></header>
      {status && <div className="settings-note">{status}</div>}
      <div className="teacher-toolbar"><div><strong>{works.length} 个作品</strong></div><div className="teacher-toolbar__actions"><button onClick={() => void review("approved", false)}>批量通过</button><button onClick={() => void review("approved", true)}>通过并精选</button><button onClick={() => void review("rejected", false)}>批量退回</button></div></div>
      <div className="backoffice-table">
        <div><span>全选</span><span>作品</span><span>类型</span><span>状态</span><span>操作</span></div>
        {works.map((work) => <div key={work.assetId}><span><input type="checkbox" checked={selected.includes(work.assetId)} onChange={(event) => setSelected((prev) => event.target.checked ? [...prev, work.assetId] : prev.filter((id) => id !== work.assetId))} /></span><strong>{work.title}<small>{work.prompt}</small></strong><span>{work.kind}</span><span className="status-pill">{work.reviewState === "approved" ? "已通过" : work.reviewState === "rejected" ? "已退回" : "待审核"}</span><span><a className="teacher-secondary-link" href={`/works/${work.assetId}`}>查看</a></span></div>)}
        {works.length === 0 && <div><span>—</span><span>暂无待审核作品</span><span>—</span><span>—</span><span>—</span></div>}
      </div>
    </main>
  );
}
