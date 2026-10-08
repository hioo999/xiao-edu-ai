"use client";

import { useEffect, useState } from "react";

import { currentSession, favoriteInspirationCase, inspirationAttachmentUrl, listInspirationCases, type InspirationCase } from "../../src/api-client";

const routeFor = (capability: InspirationCase["capability"]) => capability === "html" ? "/workspace/html" : capability === "text" ? "/workspace/chat" : `/workspace/${capability}`;
const startRouteFor = (item: InspirationCase) => `${routeFor(item.capability)}?prompt=${encodeURIComponent(item.prompt)}`;

export default function InspirationPage() {
  const [cases, setCases] = useState<InspirationCase[]>([]);
  const [message, setMessage] = useState("正在寻找适合你的灵感卡…");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const visibleCases = favoritesOnly ? cases.filter((item) => item.favorite) : cases;

  useEffect(() => {
    const session = currentSession();
    if (!session) { setMessage("登录后就能看到老师为你准备的灵感卡。"); return; }
    setSignedIn(true);
    void listInspirationCases(session.accessToken).then((items) => { setCases(items); setMessage(items.length ? "" : "老师还没有发布灵感卡，先从创作小屋开始吧！"); }).catch(() => setMessage("暂时无法读取灵感卡，请稍后再试。"));
  }, []);

  async function toggleFavorite(item: InspirationCase) {
    const session = currentSession();
    if (!session) return setMessage("请先登录后收藏灵感卡。");
    try {
      await favoriteInspirationCase(session.accessToken, item.caseId, !item.favorite);
      setCases((current) => current.map((caseItem) => caseItem.caseId === item.caseId ? { ...caseItem, favorite: !caseItem.favorite } : caseItem));
    } catch { setMessage("收藏没有成功，请稍后再试。"); }
  }

  const showNoCases = !message.includes("正在寻找") && visibleCases.length === 0;

  return <main className="student-home"><section className="student-home__content"><header className="student-home__header"><p className="student-home__eyebrow">INSPIRATION LIBRARY</p><h1>不知道做什么？从一个案例开始</h1><p className="student-home__intro">每个案例都可以直接开始，也可以复制提示词，再加入自己的想法。</p></header><div className="inspiration-tabs"><button type="button" className={!favoritesOnly ? "is-active" : ""} onClick={() => setFavoritesOnly(false)}>全部灵感</button><button type="button" className={favoritesOnly ? "is-active" : ""} onClick={() => setFavoritesOnly(true)}>♡ 我的收藏</button></div>{message && <p className="settings-note">{message}</p>}{favoritesOnly && visibleCases.length === 0 ? <section className="student-empty-state"><span>💖</span><h2>先收藏一个喜欢的灵感吧</h2><p>收藏后的案例会放在这里，下一次可以直接继续创作。</p><button type="button" className="teacher-primary-link" onClick={() => setFavoritesOnly(false)}>去看全部灵感</button></section> : showNoCases ? <section className="student-empty-state"><span>{signedIn ? "🪄" : "🔐"}</span><h2>{signedIn ? "老师正在准备新的灵感卡" : "登录后解锁你的灵感收藏夹"}</h2><p>{signedIn ? "你可以先进入创作小屋，自己试着做出第一个作品。" : "老师发布的案例、你收藏的创作点子，都会整齐保存在这里。"}</p><div className="student-empty-state__actions">{signedIn ? <a className="teacher-primary-link" href="/workspace/html">去创作网页</a> : <a className="teacher-primary-link" href="/login">学生登录</a>}<a className="teacher-secondary-link" href="/">回创作大厅</a></div></section> : <div className="student-home__grid">{visibleCases.map((item) => <article className="feature-card" key={item.caseId}><div className="feature-card__topline"><span className="feature-card__icon">✦</span><span className="feature-card__number">{item.difficulty}</span></div><h2>{item.title}</h2><p>{item.capability} · {item.durationMinutes} 分钟</p><div className="case-actions"><a className="feature-card__cta case-actions__primary" href={startRouteFor(item)}>直接开始 →</a>{item.attachmentId && <a href={inspirationAttachmentUrl(item.caseId)}>下载参考素材</a>}<button type="button" onClick={() => navigator.clipboard?.writeText(item.prompt)}>复制提示</button><button type="button" onClick={() => void toggleFavorite(item)}>{item.favorite ? "♥ 已收藏" : "♡ 收藏"}</button></div></article>)}</div>}</section></main>;
}
