"use client";

import { Bot, Code2, Image, Music2, Sparkles, Video } from "lucide-react";
import type { ReactNode } from "react";
import "./creation-surface.css";

const destinations = [
  { href: "/workspace/chat", label: "AI 对话", icon: Bot },
  { href: "/workspace/image", label: "图片创作", icon: Image },
  { href: "/workspace/html", label: "网页创作", icon: Code2 },
  { href: "/workspace/music", label: "音乐创作", icon: Music2 },
  { href: "/workspace/video", label: "视频创作", icon: Video },
  { href: "/agents", label: "智能体中心", icon: Sparkles },
];

export function CreationHeader({ title, description, active, children }: { title: string; description: string; active: string; children?: ReactNode }) {
  return <header className="creation-header">
    <div className="creation-header__brand"><a href="/">✦ 星芽 AI 创作岛</a><a href="/projects">我的作品 →</a></div>
    <nav aria-label="创作小屋导航">{destinations.map(({ href, label, icon: Icon }) => <a key={href} href={href} aria-current={active === href ? "page" : undefined}><Icon size={18} /><span>{label}</span></a>)}</nav>
    <div className="creation-header__main"><button type="button" onClick={() => window.history.length > 1 ? window.history.back() : window.location.assign("/")}>← 返回上一页</button><div><p>一起把好点子变成作品</p><h1>{title}</h1><span>{description}</span></div><div className="creation-header__actions">{children}</div></div>
  </header>;
}
