"use client";

import { useEffect, useMemo, useState } from "react";

import { CreativeWork, currentSession, listMyWorks } from "../../src/api-client";

const filters = ["全部", "图片", "音乐", "视频", "网页"] as const;
const kindLabels: Record<string, string> = { text: "文字", image: "图片", music: "音乐", video: "视频", webpage: "网页", lesson: "课程", report: "报告" };
const kindIcons: Record<string, string> = { text: "✦", image: "◉", music: "♫", video: "▶", webpage: "⌘", lesson: "▤", report: "▧" };
const filterKinds: Record<(typeof filters)[number], string | null> = { "全部": null, "图片": "image", "音乐": "music", "视频": "video", "网页": "webpage" };

export default function AssetsPage() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [filter, setFilter] = useState<(typeof filters)[number]>("全部");
  const [message, setMessage] = useState("正在加载你的创作素材…");
  const visibleWorks = useMemo(() => works.filter((work) => !filterKinds[filter] || work.kind === filterKinds[filter]), [filter, works]);

  useEffect(() => {
    const session = currentSession();
    if (!session) {
      setMessage("请先登录后查看自己的素材。");
      return;
    }
    void listMyWorks(session.accessToken).then((items) => {
      setWorks(items);
      setMessage(items.length ? "" : "还没有素材，去创作小屋完成第一件作品吧！");
    }).catch(() => setMessage("素材暂时加载失败，请稍后重试。"));
  }, []);

  return <main className="catalog-shell"><header className="catalog-header"><a href="/" className="workspace-back">← 创作大厅</a><p className="student-home__eyebrow">MY ASSETS</p><h1>我的素材</h1><p>查看你生成的图片、音乐、视频和网页，并把它们带进下一次创作。</p></header><div className="asset-toolbar">{filters.map((item) => <button type="button" key={item} className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)}>{item}</button>)}<a className="upload-button" href="/inspiration">＋ 去创作</a></div>{message && <p className="course-upload-status">{message}</p>}<div className="asset-grid">{visibleWorks.map((work) => <article className="asset-card" key={work.assetId}><div className="asset-preview">{work.previewUrl && work.kind === "image" ? <img src={work.previewUrl} alt={`${work.title}预览`} /> : <span>{kindIcons[work.kind] ?? "✦"}</span>}</div><span>{kindLabels[work.kind] ?? work.kind}</span><h2>{work.title}</h2><p>{work.prompt || "AI 创作素材"}</p><a className="teacher-primary-link" href={`/works/${work.assetId}`}>查看作品</a></article>)}</div></main>;
}
