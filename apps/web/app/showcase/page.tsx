"use client";

import { useEffect, useState } from "react";

import { CreativeWork, currentSession, getWorkInteractions, likeWork, listShowcaseWorks, resolveWorkMediaUrl } from "../../src/api-client";

const icons: Record<string, string> = { webpage: "⌘", image: "◉", music: "♫", video: "▶", text: "✦" };

export default function ShowcasePage() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [message, setMessage] = useState("正在打开同学作品展示墙…");
  const [kind, setKind] = useState("all");
  const [hearts, setHearts] = useState<Record<string, { count: number; liked: boolean }>>({});

  useEffect(() => {
    const session = currentSession();
    if (!session) { setMessage("学生登录后就可以参观同学们已审核的作品。"); return; }
    void listShowcaseWorks(session.accessToken).then(async (items) => { setWorks(items); setMessage(items.length ? "" : "老师还没有发布展示作品，期待你的第一件作品入选！"); const entries = await Promise.all(items.map(async (work) => [work.assetId, await getWorkInteractions(session.accessToken, work.assetId)] as const)); setHearts(Object.fromEntries(entries.map(([id, value]) => [id, { count: value.likeCount, liked: value.liked }]))); }).catch(() => setMessage("暂时无法读取作品展示墙。"));
  }, []);

  async function toggleHeart(work: CreativeWork) { const session = currentSession(); if (!session) return; const current = hearts[work.assetId] ?? { count: 0, liked: false }; try { const result = await likeWork(session.accessToken, work.assetId, !current.liked); setHearts((value) => ({ ...value, [work.assetId]: { count: result.likeCount, liked: result.liked } })); } catch { setMessage("小心心发送失败，请稍后再试。"); } }
  const visibleWorks = kind === "all" ? works : works.filter((work) => work.kind === kind);

  return <main className="catalog-shell"><header className="catalog-header"><a className="workspace-back" href="/projects">← 我的作品</a><p className="student-home__eyebrow">STUDENT SHOWCASE</p><h1>同学作品展示墙</h1><p>这里展示老师审核通过的作品。喜欢一个点子，就把它变成属于自己的新创作。</p></header>{message ? <section className="student-empty-state"><span>🌟</span><h2>{message}</h2><a className="teacher-primary-link" href="/workspace/html">我也去创作</a></section> : <><div className="inspiration-tabs" aria-label="作品类型筛选">{[["all", "全部"], ["webpage", "网页"], ["image", "图片"], ["music", "音乐"], ["video", "视频"]].map(([id, label]) => <button key={id} className={kind === id ? "is-active" : ""} type="button" onClick={() => setKind(id)}>{label}</button>)}</div><div className="asset-grid">{visibleWorks.map((work) => <article className="asset-card" key={work.assetId}><div className="asset-preview">{(work.coverUrl || work.previewUrl) && work.kind === "image" ? <img src={resolveWorkMediaUrl(work.coverUrl || work.previewUrl)} alt={`${work.title}预览`} /> : <span>{icons[work.kind] ?? "✦"}</span>}</div><span>{work.isExample ? "示例作品" : work.featured ? "精选作品" : "作品展示"} · 适合 {work.gradeMin}-{work.gradeMax} 年级</span><h2>{work.title}</h2><p>{work.prompt || "一件经过审核的 AI 创作作品"}</p><div className="case-actions"><button type="button" onClick={() => void toggleHeart(work)}>{hearts[work.assetId]?.liked ? "♥ 已喜欢" : "♡ 喜欢"} {hearts[work.assetId]?.count ?? 0}</button><a className="teacher-primary-link" href={`/works/${work.assetId}`}>查看作品</a></div></article>)}</div></>}</main>;
}
