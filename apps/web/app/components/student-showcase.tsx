"use client";

import { CSSProperties, useEffect, useState } from "react";

import { CreativeWork, currentSession, getStudentAccess, listShowcaseWorks, StudentAccess } from "../../src/api-client";
import { showcaseProjects } from "../../src/showcase-projects";
import { useWorkMediaUrl } from "./use-work-media-url";

const icons: Record<string, string> = { webpage: "⌘", image: "◉", music: "♫", video: "▶", text: "✦" };
const defaultSettings: Pick<StudentAccess, "showcaseColumns" | "showcaseRows" | "showcaseSort" | "showcaseKind"> = { showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all" };

function ShowcaseCover({ work }: { work: CreativeWork }) {
  const source = useWorkMediaUrl(work.kind === "image" ? work.coverUrl || work.previewUrl : "");
  return work.kind === "image" && source ? <img src={source} alt={`${work.title}封面`} /> : <><span>{work.kind}</span><b>{icons[work.kind] ?? "✦"}</b></>;
}

export function StudentShowcase() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [settings, setSettings] = useState(defaultSettings);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const session = currentSession();
    if (!session) { setLoaded(true); return; }
    void getStudentAccess(session.accessToken)
      .then(async (access) => {
        const nextSettings = { showcaseColumns: access.showcaseColumns, showcaseRows: access.showcaseRows, showcaseSort: access.showcaseSort, showcaseKind: access.showcaseKind };
        setSettings(nextSettings);
        setWorks(await listShowcaseWorks(session.accessToken, nextSettings.showcaseKind, 8, "popular"));
      })
      .catch(() => setWorks([]))
      .finally(() => setLoaded(true));
  }, []);

  const gridStyle = { "--showcase-columns": settings.showcaseColumns } as CSSProperties;
  const showExamples = loaded && works.length === 0;

  return <section className="student-showcase" aria-labelledby="showcase-title">
    <div className="student-showcase__heading"><div><p>{works.length ? "小小创造家作品展" : "创作灵感展"}</p><h2 id="showcase-title">{works.length ? "看看大家把想法变成了什么" : "从一个好点子开始创作"}</h2></div><a href="/showcase">进入作品展示墙 →</a></div>
    <div className="student-showcase__grid" style={gridStyle}>
      {works.map((work, index) => <a href={`/works/${work.assetId}`} className={`showcase-card showcase-card--${index % 4}`} key={work.assetId}>
        <div className="showcase-card__cover" style={work.kind === "image" && (work.coverUrl || work.previewUrl) ? undefined : { background: ["linear-gradient(145deg, #7e8df5, #55d7e8 55%, #fff0a8)", "linear-gradient(145deg, #7bd1a2, #b8f2d0 52%, #fff0a8)", "linear-gradient(145deg, #a98bf4, #ffb8d0 52%, #ffe18a)", "linear-gradient(145deg, #ffaf91, #ffd36e 52%, #8fbdff)"][index % 4] }}>
          <ShowcaseCover work={work} />
        </div>
        <div className="showcase-card__body"><div className="showcase-card__meta"><span>✦ 小小创作者</span>{work.featured && <em>精选</em>}</div><h3>{work.title}</h3><p>{work.prompt || "一件等待你来发现的 AI 创作作品。"}</p><div className="showcase-card__heat"><span>♥ {work.likeCount ?? 0}</span><span>☆ {work.favoriteCount ?? 0}</span></div><small>查看作品 →</small></div>
      </a>)}
      {showExamples && showcaseProjects.slice(0, 8).map((project, index) => <a href={`/works/examples/${project.id}`} className={`showcase-card showcase-card--${index % 4}`} key={project.id}>
        <div className="showcase-card__cover" style={{ background: project.cover }}><span>{project.type}</span><b>{project.type === "网页" ? "⌘" : project.type === "图片" ? "◉" : project.type === "音乐" ? "♫" : "▶"}</b></div>
        <div className="showcase-card__body"><div className="showcase-card__meta"><span>✦ 创作灵感</span>{project.featured && <em>推荐</em>}</div><h3>{project.title}</h3><p>{project.description}</p><small>查看创作提示 →</small></div>
      </a>)}
    </div>
  </section>;
}
