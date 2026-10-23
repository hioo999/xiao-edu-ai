"use client";

import { useParams } from "next/navigation";

import { showcaseProjectById } from "../../../../src/showcase-projects";

const workspaceByType = { 网页: "html", 图片: "image", 音乐: "music", 视频: "video", 文字: "chat" } as const;
const iconByType = { 网页: "⌘", 图片: "◉", 音乐: "♫", 视频: "▶", 文字: "✦" } as const;

export default function ExampleWorkDetailPage() {
  const params = useParams<{ id: string }>();
  const project = showcaseProjectById(params.id);
  if (!project) return <main className="work-detail-page"><a href="/" className="work-detail-page__back">← 回到创作岛</a><h1>这个示例作品暂时找不到了。</h1></main>;
  const workspace = workspaceByType[project.type];
  const createHref = `/workspace/${workspace}?prompt=${encodeURIComponent(project.prompt)}`;
  return <main className="work-detail-page example-work-detail">
    <a href="/" className="work-detail-page__back">← 回到创作岛</a>
    <div className="work-detail-page__layout">
      <section className="work-detail__preview">
        {project.previewUrl ? <video className="work-detail__media" controls playsInline src={project.previewUrl}>你的浏览器暂不支持视频播放。</video> : <div className="work-detail__cover work-detail__cover--example" style={{ background: project.cover }}><span>{project.type}创意</span><strong>{iconByType[project.type]}</strong><small>按提示词创作自己的作品</small></div>}
        <div className="work-detail__preview-bar"><span>{project.previewUrl ? "可播放的参考视频" : "创作灵感卡 · 非真实学生作品"}</span></div>
      </section>
      <article className="work-detail__content">
        <div className="work-detail__eyebrow">灵感案例 · {project.type}创作</div>
        <h1>{project.title}</h1>
        <p className="work-detail__student">✦ 这是一张参考创意卡，不是已上架的学生作品。</p>
        <p className="work-detail__description">{project.description}</p>
        <section><h2>可以怎样开始创作？</h2><ol className="work-detail__steps">{project.process.map((step) => <li key={step}>{step}</li>)}</ol></section>
        <section><h2>创作提示词</h2><div className="work-detail__prompt">{project.prompt}</div></section>
        <div className="work-detail__actions"><a href={createHref}>用这个灵感开始创作</a><a href="/showcase">看看更多作品</a></div>
      </article>
    </div>
  </main>;
}
