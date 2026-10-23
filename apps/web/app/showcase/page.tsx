"use client";

import { ArrowLeft, BookOpen, Bot, Code2, Heart, Image as ImageIcon, Music2, Search, Sparkles, Star, Video } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CreativeWork, currentSession, favoriteWork, likeWork, listShowcaseWorks } from "../../src/api-client";
import { useWorkMediaUrl } from "../components/use-work-media-url";
import styles from "./showcase.module.css";

type ShowcaseSort = "popular" | "newest" | "featured";
type ShowcaseKind = "all" | "webpage" | "image" | "music" | "video" | "text";
type GradeFilter = "all" | "3-4" | "5-6";
type LoadState = "loading" | "ready" | "unauthenticated" | "error";

const SORT_OPTIONS: { id: ShowcaseSort; label: string }[] = [
  { id: "popular", label: "热门" },
  { id: "newest", label: "最新" },
  { id: "featured", label: "老师精选" },
];

const KIND_OPTIONS: { id: ShowcaseKind; label: string; icon: LucideIcon }[] = [
  { id: "all", label: "全部", icon: Sparkles },
  { id: "webpage", label: "网页", icon: Code2 },
  { id: "image", label: "图片", icon: ImageIcon },
  { id: "music", label: "音乐", icon: Music2 },
  { id: "video", label: "视频", icon: Video },
  { id: "text", label: "文字", icon: BookOpen },
];

const KIND_META: Record<string, { label: string; icon: LucideIcon; tone: string }> = {
  webpage: { label: "网页", icon: Code2, tone: "violet" },
  image: { label: "图片", icon: ImageIcon, tone: "mint" },
  music: { label: "音乐", icon: Music2, tone: "pink" },
  video: { label: "视频", icon: Video, tone: "amber" },
  text: { label: "文字", icon: BookOpen, tone: "blue" },
};

function WorkCover({ work, compact = false }: { work: CreativeWork; compact?: boolean }) {
  const meta = KIND_META[work.kind] ?? KIND_META.text;
  const Icon = meta.icon;
  const imageUrl = work.coverUrl || (work.kind === "image" ? work.previewUrl : "");
  const imageSource = useWorkMediaUrl(imageUrl);
  return (
    <div className={`${styles.cover} ${styles[`cover_${meta.tone}`]} ${compact ? styles.coverCompact : ""}`}>
      {imageSource ? <img src={imageSource} alt={`${work.title}作品封面`} /> : (
        <div className={styles.coverPlaceholder} aria-hidden="true"><Icon size={compact ? 30 : 40} strokeWidth={1.8} /><span>{meta.label}创作</span></div>
      )}
      {work.kind === "video" && <span className={styles.playBadge} aria-label="视频作品"><Video size={18} fill="currentColor" /></span>}
      <span className={styles.kindBadge}><Icon size={14} aria-hidden="true" />{meta.label}</span>
    </div>
  );
}

function WorkCard({ work, onLike, onFavorite }: { work: CreativeWork; onLike: (work: CreativeWork) => Promise<void>; onFavorite: (work: CreativeWork) => Promise<void> }) {
  return (
    <article className={styles.card}>
      <a href={`/works/${work.assetId}`} className={styles.cardMain} aria-label={`查看作品：${work.title}`}>
        <WorkCover work={work} />
        <div className={styles.cardBody}>
          <div className={styles.cardMeta}><span>{work.featured ? "老师精选" : work.isExample ? "创作示例" : "同学作品"}</span><span>{work.gradeMin}-{work.gradeMax} 年级</span></div>
          <h3>{work.title}</h3>
          <p>{work.prompt || "一件经过老师审核的 AI 创作作品，点进去看看它的创作过程。"}</p>
        </div>
      </a>
      <div className={styles.cardActions}>
        <button type="button" className={work.liked ? styles.isActive : ""} aria-label={`${work.liked ? "取消点赞" : "点赞"}：${work.title}`} aria-pressed={Boolean(work.liked)} onClick={() => void onLike(work)}><Heart size={17} fill={work.liked ? "currentColor" : "none"} /><span>{work.likeCount ?? 0}</span></button>
        <button type="button" className={work.favorited ? styles.isFavorite : ""} aria-label={`${work.favorited ? "取消收藏" : "收藏"}：${work.title}`} aria-pressed={Boolean(work.favorited)} onClick={() => void onFavorite(work)}><Star size={17} fill={work.favorited ? "currentColor" : "none"} /><span>{work.favoriteCount ?? 0}</span></button>
        <a href={`/works/${work.assetId}`} className={styles.viewLink}>查看作品</a>
      </div>
    </article>
  );
}

export default function ShowcasePage() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [sort, setSort] = useState<ShowcaseSort>("popular");
  const [kind, setKind] = useState<ShowcaseKind>("all");
  const [grade, setGrade] = useState<GradeFilter>("all");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const session = currentSession();
    if (!session) { setLoadState("unauthenticated"); return; }
    let cancelled = false;
    setLoadState("loading");
    setNotice("");
    void listShowcaseWorks(session.accessToken, undefined, 100, sort)
      .then((items) => { if (!cancelled) { setWorks(items); setLoadState("ready"); } })
      .catch(() => { if (!cancelled) setLoadState("error"); });
    return () => { cancelled = true; };
  }, [sort]);

  const visibleWorks = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    return works.filter((work) => {
      const matchesKind = kind === "all" || work.kind === kind;
      const matchesGrade = grade === "all" || (grade === "3-4" ? work.gradeMin <= 4 && work.gradeMax >= 3 : work.gradeMin <= 6 && work.gradeMax >= 5);
      const matchesQuery = !normalizedQuery || `${work.title} ${work.prompt}`.toLocaleLowerCase("zh-CN").includes(normalizedQuery);
      return matchesKind && matchesGrade && matchesQuery;
    });
  }, [grade, kind, query, works]);

  const featuredWorks = visibleWorks.filter((work) => work.featured).slice(0, 4);
  const featuredIds = new Set(featuredWorks.map((work) => work.assetId));
  const galleryWorks = visibleWorks.filter((work) => !featuredIds.has(work.assetId));
  const totalLikes = works.reduce((total, work) => total + (work.likeCount ?? 0), 0);

  function updateWork(assetId: string, update: Partial<CreativeWork>) {
    setWorks((items) => items.map((work) => work.assetId === assetId ? { ...work, ...update } : work));
  }

  async function toggleLike(work: CreativeWork) {
    const session = currentSession();
    if (!session) return;
    try { updateWork(work.assetId, await likeWork(session.accessToken, work.assetId, !work.liked)); }
    catch { setNotice("点赞没有成功，请稍后再试。"); }
  }

  async function toggleFavorite(work: CreativeWork) {
    const session = currentSession();
    if (!session) return;
    try { updateWork(work.assetId, await favoriteWork(session.accessToken, work.assetId, !work.favorited)); }
    catch { setNotice("收藏没有成功，请稍后再试。"); }
  }

  const noResults = loadState === "ready" && visibleWorks.length === 0;

  return (
    <main className={styles.page}>
      <nav className={styles.topbar} aria-label="作品墙导航">
        <a href="/" className={styles.backLink}><ArrowLeft size={18} />返回创作岛</a>
        <div className={styles.topActions}><a href="/projects">我的作品</a><a href="/workspace/html" className={styles.createButton}><Sparkles size={17} />去创作</a></div>
      </nav>

      <header className={styles.hero}>
        <div className={styles.heroCopy}><p className={styles.eyebrow}><Sparkles size={16} />STUDENT SHOWCASE</p><h1>同学作品展示墙</h1><p>发现同学们的奇妙作品，看看他们怎样把一个小点子变成图片、音乐、视频和互动网页。</p></div>
        <div className={styles.stats} aria-label="作品墙统计"><div><strong>{works.length}</strong><span>作品总数</span></div><div><strong>{works.filter((work) => work.featured).length}</strong><span>老师精选</span></div><div><strong>{totalLikes}</strong><span>收获喜欢</span></div></div>
      </header>

      {loadState === "unauthenticated" ? (
        <section className={styles.statePanel}><Bot size={48} aria-hidden="true" /><h2>登录后参观同学们的作品</h2><p>作品墙只展示老师审核通过的内容，登录后还可以点赞、收藏并查看创作过程。</p><div><a href="/login?next=%2Fshowcase" className={styles.primaryAction}>登录查看</a><a href="/inspiration" className={styles.secondaryAction}>先看灵感案例</a></div></section>
      ) : (
        <>
          <section className={styles.toolbar} aria-label="筛选作品">
            <div className={styles.sortTabs} aria-label="作品排序">{SORT_OPTIONS.map((option) => <button key={option.id} type="button" className={sort === option.id ? styles.selected : ""} aria-pressed={sort === option.id} onClick={() => setSort(option.id)}>{option.label}</button>)}</div>
            <label className={styles.searchBox}><Search size={18} aria-hidden="true" /><span className={styles.srOnly}>搜索作品</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索作品名称或创意" /></label>
            <div className={styles.filterRow}>
              <div className={styles.kindFilters} aria-label="作品类型">{KIND_OPTIONS.map((option) => { const Icon = option.icon; return <button key={option.id} type="button" className={kind === option.id ? styles.selected : ""} aria-pressed={kind === option.id} onClick={() => setKind(option.id)}><Icon size={16} />{option.label}</button>; })}</div>
              <label className={styles.gradeFilter}>适用年级<select value={grade} onChange={(event) => setGrade(event.target.value as GradeFilter)}><option value="all">全部年级</option><option value="3-4">3-4 年级</option><option value="5-6">5-6 年级</option></select></label>
            </div>
          </section>

          {notice && <div className={styles.notice} role="status">{notice}<button type="button" onClick={() => setNotice("")} aria-label="关闭提示">×</button></div>}
          {loadState === "loading" && <section className={styles.skeletonGrid} aria-label="正在加载作品">{Array.from({ length: 8 }, (_, index) => <div className={styles.skeletonCard} key={index}><span /><i /><i /></div>)}</section>}
          {loadState === "error" && <section className={styles.statePanel}><Bot size={48} aria-hidden="true" /><h2>作品墙暂时没有打开</h2><p>请检查网络连接，或者稍后重新进入作品墙。</p><button type="button" className={styles.primaryAction} onClick={() => setSort((value) => value === "popular" ? "featured" : "popular")}>重新加载</button></section>}
          {noResults && <section className={styles.statePanel}><Search size={48} aria-hidden="true" /><h2>{works.length ? "没有找到符合条件的作品" : "老师还没有发布展示作品"}</h2><p>{works.length ? "换一个类型、年级或搜索词再看看。" : "先去灵感库找一个喜欢的主题，创作你的第一件作品吧。"}</p><div>{works.length ? <button type="button" className={styles.primaryAction} onClick={() => { setKind("all"); setGrade("all"); setQuery(""); }}>清除筛选</button> : <a href="/workspace/html" className={styles.primaryAction}>开始创作</a>}<a href="/inspiration" className={styles.secondaryAction}>去灵感库</a></div></section>}

          {loadState === "ready" && featuredWorks.length > 0 && <section className={styles.featuredSection} aria-labelledby="featured-heading"><div className={styles.sectionHeading}><div><span>TEACHER PICKS</span><h2 id="featured-heading">老师精选</h2></div><p>老师挑选的好点子，先从这里开始逛。</p></div><div className={styles.featuredGrid}>{featuredWorks.map((work) => <a href={`/works/${work.assetId}`} className={styles.featuredCard} key={work.assetId} aria-label={`老师精选：${work.title}`}><WorkCover work={work} compact /><div><span><Star size={14} fill="currentColor" />精选作品</span><h3>{work.title}</h3><p>{work.prompt || "看看这件作品是怎样完成的。"}</p></div></a>)}</div></section>}
          {loadState === "ready" && galleryWorks.length > 0 && <section className={styles.gallerySection} aria-labelledby="gallery-heading"><div className={styles.sectionHeading}><div><span>EXPLORE WORKS</span><h2 id="gallery-heading">发现更多作品</h2></div><p>找到喜欢的作品，可以收藏起来慢慢研究。</p></div><div className={styles.galleryGrid}>{galleryWorks.map((work) => <WorkCard key={work.assetId} work={work} onLike={toggleLike} onFavorite={toggleFavorite} />)}</div></section>}
        </>
      )}
    </main>
  );
}
