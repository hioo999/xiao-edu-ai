"use client";

import { useEffect, useMemo, useState } from "react";

import { createMediaJob, createWork, currentSession, dispatchAgent, generateHtml, generateText, listAgents, type ManagedAgent } from "../../src/api-client";

type AgentView = ManagedAgent & { icon: string; color: string; label: string; route: string; description: string; steps: string[] };

const capabilityMeta: Record<ManagedAgent["capability"], { label: string; icon: string; color: string; route: string; description: string; steps: string[] }> = {
  text: { label: "文字创作", icon: "✦", color: "blue", route: "/workspace/chat", description: "把想法说清楚、写成故事和方案", steps: ["说出你想完成的事情", "和 AI 一起完善内容", "保存你的创作版本"] },
  html: { label: "网页创作", icon: "⌘", color: "violet", route: "/workspace/html", description: "用自然语言做出可以预览的网页", steps: ["说清楚网页主题", "一起完善页面内容", "预览并下载作品"] },
  image: { label: "图片创作", icon: "◉", color: "pink", route: "/workspace/image", description: "把角色、场景和故事变成画面", steps: ["想好画面主角", "选择画面风格", "生成并收藏作品"] },
  video: { label: "视频创作", icon: "▶", color: "green", route: "/workspace/video", description: "把故事拆成镜头并生成动态作品", steps: ["安排故事镜头", "补充画面和动作", "等待作品生成"] },
  music: { label: "音乐创作", icon: "♫", color: "amber", route: "/workspace/music", description: "把主题变成歌词和音乐灵感", steps: ["说出歌曲主题", "选择音乐方向", "保存创作想法"] },
};

const fallbackAgents: AgentView[] = [
  { agentId: "web-coach", name: "网页创作伙伴", capability: "html", gradeRange: "4-6", published: true, ...capabilityMeta.html },
  { agentId: "writing-coach", name: "写作小老师", capability: "text", gradeRange: "3-6", published: true, ...capabilityMeta.text },
  { agentId: "painting-coach", name: "绘画灵感师", capability: "image", gradeRange: "3-6", published: true, ...capabilityMeta.image },
  { agentId: "video-coach", name: "视频故事导演", capability: "video", gradeRange: "4-6", published: true, ...capabilityMeta.video },
];

function enrichAgent(agent: ManagedAgent): AgentView {
  return { ...agent, ...(capabilityMeta[agent.capability] ?? capabilityMeta.text) };
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentView[]>(fallbackAgents);
  const [selectedId, setSelectedId] = useState(fallbackAgents[0].agentId);
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState("");
  const [htmlPreview, setHtmlPreview] = useState("");
  const [status, setStatus] = useState("选择一个 AI 伙伴，直接说出你想完成的事情。");
  const [busy, setBusy] = useState(false);
  const selected = useMemo(() => agents.find((agent) => agent.agentId === selectedId) ?? agents[0], [agents, selectedId]);

  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    void listAgents(session.accessToken).then((items) => {
      const next = items.filter((item) => item.published).map(enrichAgent);
      if (next.length) {
        setAgents(next);
        setSelectedId(next[0].agentId);
      }
    }).catch(() => setStatus("暂时使用平台内置 AI 伙伴，稍后会自动同步最新配置。"));
  }, []);

  async function submit() {
    const value = prompt.trim();
    const session = currentSession();
    if (!value) return setStatus("先告诉我你想完成什么吧。");
    if (!session) return setStatus("请先登录平台账号，再开始使用智能体。");
    setBusy(true);
    setResult("");
    setHtmlPreview("");
    setStatus(`${selected.name}正在理解你的任务…`);
    try {
      await dispatchAgent(session.accessToken, { agentId: selected.agentId, prompt: value });
      if (selected.capability === "html") {
        const generated = await generateHtml(session.accessToken, `agent-web-${session.userId}`, value);
        setHtmlPreview(generated.currentVersion.html);
        setResult("网页已经生成，可以在右侧预览；也可以进入网页创作继续修改。");
        setStatus("网页创作完成，已保留到作品历史。");
      } else if (selected.capability === "text") {
        const generated = await generateText(session.accessToken, value);
        await createWork(session.accessToken, { projectId: `agent-text-${session.userId}`, kind: "text", title: `智能体创作：${value.slice(0, 18)}`, prompt: value });
        setResult(generated.content);
        setStatus("文字创作完成，已保存到作品历史。");
      } else if (selected.capability === "image" || selected.capability === "video") {
        const job = await createMediaJob(session.accessToken, selected.capability, value);
        setResult(`任务已进入生成队列，当前状态：${job.state}。生成完成后会自动进入作品历史。`);
        setStatus(`${selected.name}已提交创作任务。`);
      } else {
        setResult("这个智能体已经收到任务，请进入音乐创作工作台继续完成。 ");
        setStatus("已为你准备音乐创作任务。");
      }
      setPrompt("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "智能体暂时无法完成任务，请稍后再试。");
    } finally { setBusy(false); }
  }

  return <main className="agent-center-page">
    <header className="agent-center-header"><a href="/" className="workspace-back">← 回到创作岛</a><div><p className="student-home__eyebrow">AGENT CENTER</p><h1>智能体中心</h1><p>这里是统一的 AI 创作入口。你只要说出目标，智能体会帮你调用文字、网页、图片或视频能力。</p></div><a href="/projects" className="agent-center-header__projects">我的作品夹 →</a></header>
    <section className="agent-center-layout">
      <aside className="agent-roster" aria-label="智能体列表"><div className="agent-roster__title"><strong>我的 AI 伙伴</strong><span>{agents.length} 位</span></div>{agents.map((agent) => <button type="button" className={`agent-roster__item${selected.agentId === agent.agentId ? " is-selected" : ""}`} onClick={() => { setSelectedId(agent.agentId); setStatus(`已选择${agent.name}，告诉它你想完成什么。`); }} key={agent.agentId}><span className={`agent-roster__icon agent-roster__icon--${agent.color}`}>{agent.icon}</span><span><b>{agent.name}</b><small>{agent.gradeRange} 年级 · {agent.label}</small></span><i>›</i></button>)}</aside>
      <article className="agent-brief"><div className={`agent-brief__avatar agent-brief__avatar--${selected.color}`}>{selected.icon}</div><p className="agent-brief__tag">{selected.label} · 可直接使用</p><h2>{selected.name}</h2><p className="agent-brief__description">{selected.description}。不需要学习复杂配置，也不用打开代码。</p><div className="agent-brief__steps"><h3>它会这样陪你完成</h3>{selected.steps.map((step, index) => <div key={step}><b>{index + 1}</b><span>{step}</span></div>)}</div><div className="agent-task-box"><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder={`例如：${selected.capability === "html" ? "做一个介绍校园植物的互动网页" : selected.capability === "image" ? "画一只在月球上种花的小兔子" : selected.capability === "video" ? "让小机器人在教室里发现一扇星星门" : "写一个关于友谊和勇气的故事"}`} /><div><span>{status}</span><button type="button" disabled={busy} onClick={() => void submit()}>{busy ? "创作中…" : "开始创作 →"}</button></div></div>{result && <div className="agent-result"><h3>创作结果</h3><p>{result}</p>{htmlPreview && <iframe title="智能体网页预览" sandbox="allow-scripts" srcDoc={htmlPreview} />}</div>}<a className="agent-brief__start" href={selected.route}>进入{selected.label}工作台 →</a></article>
    </section>
  </main>;
}
