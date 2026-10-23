"use client";

import { useRef, useState } from "react";
import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import { currentSession, importInspirationCase, type InspirationCase } from "../../../src/api-client";

export default function InspirationAdminPage() {
  const [title, setTitle] = useState(""); const [prompt, setPrompt] = useState(""); const [capability, setCapability] = useState<InspirationCase["capability"]>("html"); const [status, setStatus] = useState(""); const [busy, setBusy] = useState(false); const fileRef = useRef<HTMLInputElement>(null);
  async function submit() { const session = currentSession(); if (!session || !title.trim() || !prompt.trim()) return setStatus("请填写灵感标题和提示词。"); setBusy(true); try { await importInspirationCase(session.accessToken, { title, prompt, capability, gradeMin: 3, gradeMax: 6, difficulty: "入门", durationMinutes: 20, interests: "创意", file: fileRef.current?.files?.[0] }); setTitle(""); setPrompt(""); if (fileRef.current) fileRef.current.value = ""; setStatus("灵感卡已发布，学生现在可以收藏并开始创作。"); } catch { setStatus("灵感素材上传失败，请检查登录和文件大小。"); } finally { setBusy(false); } }
  return <AdminShell active="/admin/inspiration"><AdminPageLayout eyebrow="INSPIRATION LIBRARY" title="灵感库" description="把案例、参考素材和提示词打包成学生可以直接开始的灵感卡。"><AdminSection title="发布灵感卡" description="标题和提示词会直接展示给学生，参考素材用于帮助学生理解创作方向。"><div className="settings-form"><label>灵感标题<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：会讲故事的星空网页" /></label><label>创作类型<select value={capability} onChange={(event) => setCapability(event.target.value as InspirationCase["capability"])}><option value="html">网页</option><option value="text">文字</option><option value="image">图片</option><option value="music">音乐</option><option value="video">视频</option></select></label><label>给学生的提示词<textarea rows={8} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="描述这张灵感卡要怎么开始创作" /></label><label>参考素材（可选）<input ref={fileRef} type="file" accept="image/*,audio/*,video/*,.html,.pdf,.zip" /></label><button type="button" className="admin-primary-button" disabled={busy} onClick={() => void submit()}>{busy ? "正在发布…" : "发布灵感卡"}</button></div>{status && <div className="admin-feedback" role="status">{status}</div>}</AdminSection></AdminPageLayout></AdminShell>;
}
