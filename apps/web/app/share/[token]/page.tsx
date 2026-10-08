"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { CreativeWork, getPublicShare } from "../../../src/api-client";

function SharedPreview({ work }: { work: CreativeWork }) {
  if (work.kind === "image" && work.previewUrl) return <img className="work-detail__media" src={work.previewUrl} alt={`${work.title}作品预览`} />;
  if (work.kind === "video" && work.previewUrl) return <video className="work-detail__media" controls src={work.previewUrl}>你的浏览器暂不支持视频播放。</video>;
  if (work.kind === "music" && work.previewUrl) return <div className="work-detail__audio"><span>♫</span><audio controls src={work.previewUrl}>你的浏览器暂不支持音频播放。</audio></div>;
  return <div className="work-detail__cover" style={{ background: "linear-gradient(145deg, #7e8df5, #55d7e8 55%, #fff0a8)" }}><span>{work.kind}</span><strong>{work.kind === "webpage" ? "⌘" : work.kind === "image" ? "◉" : work.kind === "music" ? "♫" : work.kind === "video" ? "▶" : "✦"}</strong><small>{work.kind === "webpage" ? "网页作品" : "作品预览"}</small></div>;
}

export default function SharedWorkPage() {
  const params = useParams<{ token: string }>();
  const [work, setWork] = useState<CreativeWork | null>(null);
  const [message, setMessage] = useState("正在打开分享作品…");

  useEffect(() => { if (params.token) void getPublicShare(params.token).then((result) => { setWork(result.work); setMessage(""); }).catch((error) => setMessage(error instanceof Error ? error.message : "分享链接无法打开")); }, [params.token]);

  if (!work) return <main className="catalog-shell"><a href="/" className="workspace-back">← 创作大厅</a><h1>{message}</h1></main>;
  return <main className="catalog-shell"><a href="/" className="workspace-back">← 创作大厅</a><header className="catalog-header"><p className="student-home__eyebrow">SHARED CREATION</p><h1>{work.title}</h1><p>{work.kind} 作品 · 来自 AI 创造力学习工作台</p></header><section className="work-detail-page"><div className="work-detail-page__layout"><div className="work-detail__preview"><SharedPreview work={work} /></div><article className="work-detail__content"><div className="work-detail__eyebrow">已审核通过 · 学生作品</div><h2>创作说明</h2><p>{work.prompt || "每一个想法都值得被看见。"}</p><a className="teacher-primary-link" href="/">我也要开始创作</a></article></div></section></main>;
}
