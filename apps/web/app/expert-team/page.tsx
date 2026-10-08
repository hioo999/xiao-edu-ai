"use client";

import { useState } from "react";

const teams = [
  { name: "网页创作小队", roles: ["策划员", "设计师", "检查员"], goal: "一起完成一个可以预览的互动网页", route: "/workspace/html", cta: "进入网页创作" },
  { name: "校园故事小队", roles: ["采访员", "编剧", "插画师"], goal: "把校园观察变成图文故事", route: "/workspace/chat", cta: "进入文字创作" },
  { name: "小小导演组", roles: ["导演", "摄影师", "配音师"], goal: "完成一个 30 秒主题短视频", route: "/workspace/video", cta: "进入视频创作" },
];

export default function ExpertTeamPage() {
  const [selected, setSelected] = useState<{ name: string; roles: string[]; goal: string } | null>(null);
  return <main className="catalog-shell"><header className="catalog-header"><a href="/" className="workspace-back">← 创作大厅</a><p className="student-home__eyebrow">EXPERT TEAM</p><h1>专家团协作</h1><p>你只需要说清楚目标，团队会自动分工、讨论和汇总结果。</p></header><div className="team-grid">{teams.map((team) => <article className="team-card" key={team.name}><div className="team-roles">{team.roles.join(" · ")}</div><h2>{team.name}</h2><p>{team.goal}</p><button onClick={() => setSelected(team)}>召集团队</button></article>)}</div>{selected && <section className="team-plan"><div className="team-plan__head"><div><p className="student-home__eyebrow">TEAM PLAN</p><h2>{selected.name} · 分工计划</h2></div><button type="button" onClick={() => setSelected(null)}>收起</button></div><ol>{selected.roles.map((role, index) => <li key={role}><b>{index + 1}. {role}</b><span>{["先明确目标，收集你的想法", "把想法变成草稿和方案", "检查、修改并完成最终作品"][index]}</span></li>)}</ol><p>团队目标：{selected.goal}。你可以把这个计划当作脚手架，直接进入对应创作小屋开始动手。</p><a className="teacher-primary-link" href={teams.find((team) => team.name === selected.name)!.route}>{teams.find((team) => team.name === selected.name)!.cta} →</a></section>}</main>;
}
