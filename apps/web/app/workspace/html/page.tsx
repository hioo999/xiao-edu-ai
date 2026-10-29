"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Download, Gamepad2 } from "lucide-react";
import { currentSession, generateHtml, getHtmlProject, polishPrompt } from "../../../src/api-client";
import "./html-workspace.css";
import { CreationHeader } from "../../components/creation-header";
import { creationRequest, type HtmlWorkspaceProject, type HtmlVersionSummary } from "../../../src/creation-api";

const demoHtml = `<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;font-family:system-ui;background:radial-gradient(circle at 20% 20%,#fff5c2,transparent 35%),linear-gradient(145deg,#dcf3ff,#efebff 65%,#ffe9f3);color:#33466e;min-height:100vh;display:grid;place-items:center">
    <main style="text-align:center;margin:24px;padding:38px 26px;border:3px solid white;border-radius:32px;background:#ffffffcf;box-shadow:0 18px 40px #6678aa20"><div style="font-size:64px">🚀 🌟</div><p style="letter-spacing:.12em;color:#8b72d8;font-size:12px;font-weight:800">我的第一个互动网页</p><h1>我的太空探险</h1><p id="message">点击按钮，开始探索星球。</p><button onclick="document.getElementById('message').textContent='发现一颗会发光的蓝色星球！';this.textContent='继续探索'" style="border:3px solid white;border-radius:18px;padding:14px 24px;background:#8976e5;color:white;box-shadow:0 5px 0 #6856c0;font-weight:800;cursor:pointer">开始探索</button><p style="margin-top:25px;font-size:12px;color:#8593b0">你也可以在左边写下想法，创造自己的奇妙世界。</p></main>
  </body>
</html>`;

const webExamples = [
  { icon: "📖", title: "魔法书首页", prompt: "做一个魔法书首页，点击按钮后出现会发光的咒语卡片。" },
  { icon: "🏰", title: "森林城堡", prompt: "做一个森林城堡介绍页，有标题、三张作品卡片和一个探索按钮。" },
  { icon: "🌈", title: "小小天气站", prompt: "做一个小小天气站，展示晴天、雨天、彩虹天三种卡片。" },
  { icon: "⭐", title: "星星小游戏", prompt: "做一个收集星星的小游戏首页，颜色明亮，按钮要大一点。" },
];

export default function HtmlWorkspacePage() {
  const [prompt, setPrompt] = useState("");
  const [activeTab, setActiveTab] = useState<"tutorial" | "preview">("preview");
  const [html, setHtml] = useState(demoHtml);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "你好！告诉我你想做什么网页，我会一步一步陪你完成。" },
  ]);
  const starterTutorial = useMemo(() => [
    "先说清楚网页主题：这是一个关于什么的网页？",
    "再告诉我你希望访客看到什么、点击什么。",
    "最后一起检查颜色、文字和按钮是否适合你的作品。",
  ], []);
  const [tutorial, setTutorial] = useState(starterTutorial);
  const [polishing, setPolishing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [loginRequired, setLoginRequired] = useState(false);
  const previewRef = useRef<HTMLElement>(null);
  const previewDialogRef = useRef<HTMLDialogElement>(null);
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<{ projectId: string; title: string }[]>([]);
  const [versions, setVersions] = useState<HtmlVersionSummary[]>([]);
  const [versionId, setVersionId] = useState("");
  const [currentVersionId, setCurrentVersionId] = useState("");
  const [versionBusy, setVersionBusy] = useState(false);

  function showProject(project: HtmlWorkspaceProject) {
    setHtml(project.currentVersion.html);
    setTutorial(project.currentVersion.teachingSteps);
    setVersions(project.versions ?? [project.currentVersion]);
    setVersionId(project.currentVersion.versionId);
    setCurrentVersionId(project.currentVersionId ?? project.currentVersion.versionId);
  }

  async function openProject(id: string) {
    const session = currentSession();
    if (!session) return;
    setVersionBusy(true);
    try {
      const project = await getHtmlProject(session.accessToken, id) as HtmlWorkspaceProject | null;
      setProjectId(id);
      window.localStorage.setItem(`html-project:${session.organizationId}:${session.userId}`, id);
      if (project) showProject(project);
      else { setHtml(demoHtml); setVersions([]); setVersionId(""); setCurrentVersionId(""); }
    } catch (error) { setMessages((current) => [...current, { role: "assistant", text: error instanceof Error ? error.message : "网页暂时无法打开。" }]); }
    finally { setVersionBusy(false); }
  }

  useEffect(() => {
    const starterPrompt = new URLSearchParams(window.location.search).get("prompt")?.trim() ?? "";
    if (starterPrompt) setPrompt(starterPrompt);
    const session = currentSession();
    if (!session || session.role !== "student") return;
    const selected = new URLSearchParams(window.location.search).get("projectId") || window.localStorage.getItem(`html-project:${session.organizationId}:${session.userId}`) || `web-${session.userId}`;
    setProjectId(selected);
    void creationRequest<{ projects: { projectId: string; title: string }[] }>(session.accessToken, "/projects/html").then((data) => setProjects(data.projects)).catch(() => {});
    setVersionBusy(true);
    void getHtmlProject(session.accessToken, selected).then((project) => {
      if (!project) return;
      showProject(project as HtmlWorkspaceProject);
      setMessages((current) => [...current, { role: "assistant", text: "已找回你上次创作的网页，可以继续修改，也可以直接预览和下载。" }]);
    }).catch(() => setMessages((current) => [...current, { role: "assistant", text: "上次的网页暂时无法读取，请刷新重试。" }])).finally(() => setVersionBusy(false));
  }, []);

  async function submitPrompt() {
    const value = prompt.trim();
    if (!value || generating || versionBusy || (versionId && versionId !== currentVersionId)) return;
    const session = currentSession();
    if (!session || session.role !== "student") {
      setLoginRequired(true);
      return;
    }
    setLoginRequired(false);
    setGenerating(true);
    setMessages((current) => [...current, { role: "student", text: value }]);
    setPrompt("");
    try {
      const selectedProject = projectId || `web-${session.userId}`;
      const generated = await generateHtml(session.accessToken, selectedProject, value);
      showProject(generated);
      setProjects((current) => [{ projectId: selectedProject, title: generated.currentVersion.title }, ...current.filter((project) => project.projectId !== selectedProject)]);
      window.localStorage.setItem(`html-project:${session.organizationId}:${session.userId}`, selectedProject);
      const saved = await getHtmlProject(session.accessToken, selectedProject).catch(() => null);
      if (saved) showProject(saved as HtmlWorkspaceProject);
      setMessages((current) => [...current, { role: "assistant", text: "新版本已经生成，可以在右侧预览，并查看每一步学习提示。" }]);
      setActiveTab("preview");
    } catch (error) {
      const message = error instanceof Error ? error.message : "网页创作服务暂时不可用，请稍后再试。";
      setMessages((current) => [...current, { role: "assistant", text: message }]);
    } finally { setGenerating(false); }
  }

  async function polish() {
    const value = prompt.trim();
    const session = currentSession();
    if (!session || session.role !== "student") { setLoginRequired(true); return; }
    if (!value) return setMessages((current) => [...current, { role: "assistant", text: "先写下一点网页想法，再让我帮你润色吧。" }]);
    setPolishing(true);
    try {
      const result = await polishPrompt(session.accessToken, "html", value);
      setPrompt(result.content);
      setMessages((current) => [...current, { role: "assistant", text: "我已经把你的网页想法整理好了。你可以继续修改，或直接发送生成网页。" }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", text: error instanceof Error ? error.message : "润色暂时不可用，请稍后再试。" }]);
    } finally { setPolishing(false); }
  }

  function download(name: string, content: BlobPart, type: string) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function openPreview() {
    setActiveTab("preview");
    previewDialogRef.current?.showModal();
  }

  function newProject() {
    const session = currentSession();
    if (!session) { setLoginRequired(true); return; }
    const id = `web-${session.userId}-${crypto.randomUUID()}`;
    setProjectId(id);
    window.localStorage.setItem(`html-project:${session.organizationId}:${session.userId}`, id);
    setHtml(demoHtml); setVersions([]); setVersionId(""); setCurrentVersionId(""); setPrompt("");
    setMessages([{ role: "assistant", text: "新网页准备好了，说说这次想做什么吧！之前的作品都保留在历史网页里。" }]);
  }

  async function previewVersion(id: string) {
    const session = currentSession();
    if (!session || !id) return;
    setVersionBusy(true);
    try {
      const saved = await creationRequest<HtmlWorkspaceProject>(session.accessToken, `/projects/${encodeURIComponent(projectId)}/html/versions/${encodeURIComponent(id)}`);
      setHtml(saved.currentVersion.html); setTutorial(saved.currentVersion.teachingSteps); setVersionId(id);
    } catch { setMessages((current) => [...current, { role: "assistant", text: "这个版本暂时无法预览，请重试。" }]); }
    finally { setVersionBusy(false); }
  }

  async function restoreVersion() {
    const session = currentSession();
    if (!session || !versionId) return;
    setVersionBusy(true);
    try {
      await creationRequest(session.accessToken, `/projects/${encodeURIComponent(projectId)}/html/versions/${encodeURIComponent(versionId)}/restore`, "POST", {});
      await openProject(projectId);
      setMessages((current) => [...current, { role: "assistant", text: "已恢复所选版本，接下来会基于这个版本继续修改。" }]);
    } catch { setMessages((current) => [...current, { role: "assistant", text: "恢复没有完成，请重试。" }]); }
    finally { setVersionBusy(false); }
  }

  async function copyTutorial() {
    try {
      await navigator.clipboard.writeText(tutorial.map((step, index) => (index + 1) + ". " + step).join("\n"));
      setMessages((current) => [...current, { role: "assistant", text: "指导步骤已复制，可以粘贴到学习笔记里。" }]);
    } catch { setMessages((current) => [...current, { role: "assistant", text: "复制没有完成，可以点击下载指导保存到电脑。" }]); }
  }

  return (
    <main className="workspace-shell html-workspace creation-surface">
      <dialog ref={previewDialogRef} className="html-preview-dialog" aria-label="网页全屏预览"><div><strong>我的网页 · 试玩预览</strong><button type="button" onClick={() => previewDialogRef.current?.close()}>关闭预览</button></div><iframe title="网页全屏预览" sandbox="allow-scripts" srcDoc={html} /></dialog>
      <CreationHeader title="网页创作工作台" description="写下想法 → 生成网页 → 预览和改进" active="/workspace/html"><a href="/play"><Gamepad2 size={16} /> 先试玩小游戏</a><button type="button" onClick={openPreview}>打开网页预览</button><button type="button" onClick={() => download("my-webpage.html", html, "text/html")}><Download size={15} /> 下载 HTML</button><button type="button" onClick={() => download("teaching-steps.txt", tutorial.join("\n"), "text/plain")}><BookOpen size={15} /> 下载指导</button></CreationHeader>
      <section className="workspace-grid">
        <aside className="chat-panel">
          <div className="html-project-bar"><label>历史网页<select aria-label="选择历史网页" disabled={generating || versionBusy} value={projectId} onChange={(event) => void openProject(event.target.value)}><option value={projectId}>{projects.find((project) => project.projectId === projectId)?.title || "当前网页"}</option>{projects.filter((project) => project.projectId !== projectId).map((project) => <option key={project.projectId} value={project.projectId}>{project.title}</option>)}</select></label><button type="button" disabled={generating} onClick={newProject}>＋ 新建网页</button></div>
          <div className="panel-heading"><strong>✦ 和网页创作伙伴对话</strong><span>不需要写代码</span></div>
          <div className="chat-messages">
            {messages.map((message, index) => <div className={`chat-bubble chat-bubble--${message.role}`} key={`${message.role}-${index}`}>{message.text}</div>)}
          </div>
          {loginRequired && <div className="html-workspace__notice" role="alert">先用老师分配的平台学生账号登录，就能生成和保存网页。<a href="/login?next=%2Fworkspace%2Fhtml">去登录 →</a></div>}
          <div className="prompt-box"><label htmlFor="html-idea">描述你想做的网页</label><textarea id="html-idea" value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submitPrompt(); } }} placeholder="例如：把标题改成海底探险，颜色更明亮" /><div className="html-workspace__composer-actions"><button type="button" disabled={polishing || generating} onClick={() => void polish()}>{polishing ? "润色中…" : "✨ 帮我润色"}</button><button type="button" disabled={generating || versionBusy || (Boolean(versionId) && versionId !== currentVersionId) || !prompt.trim()} onClick={() => void submitPrompt()}>{generating ? "正在生成…" : "发送并生成"}</button></div>{versionId && versionId !== currentVersionId && <small>正在查看历史版本，先恢复此版本，再继续修改。</small>}</div>
          <div className="web-example-grid" aria-label="网页创作示例">
            <p>没想法？试试这些灵感</p>
            {webExamples.map((example) => <button type="button" key={example.title} onClick={() => setPrompt(example.prompt)}><span aria-hidden="true">{example.icon}</span><b>{example.title}</b><small>{example.prompt}</small></button>)}
          </div>
        </aside>
        <section className="preview-panel" ref={previewRef}>
          {versions.length > 0 && <div className="html-project-bar"><label>历史版本<select aria-label="选择历史版本" disabled={generating || versionBusy} value={versionId} onChange={(event) => void previewVersion(event.target.value)}>{versions.map((version, index) => <option key={version.versionId} value={version.versionId}>第 {index + 1} 版 · {version.title}</option>)}</select></label><button type="button" disabled={versionBusy || generating || versionId === currentVersionId} onClick={() => void restoreVersion()}>恢复此版本</button></div>}
          <div className="workspace-tabs"><button className={activeTab === "preview" ? "is-active" : ""} onClick={() => setActiveTab("preview")}>预览</button><button className={activeTab === "tutorial" ? "is-active" : ""} onClick={() => setActiveTab("tutorial")}>教程</button></div>
          {activeTab === "preview" ? <iframe title="网页预览" sandbox="allow-scripts" srcDoc={html} className="html-preview" /> : <div className="tutorial-panel"><h2>这一步你学会了什么？</h2><button type="button" className="tutorial-copy" onClick={() => void copyTutorial()}>复制全部指导步骤</button>{tutorial.map((step, index) => <div className="tutorial-step" key={step}><span>{index + 1}</span><p>{step}</p></div>)}<p className="tutorial-tip">小提示：你可以继续用自然语言要求修改，不需要打开代码。</p></div>}
        </section>
      </section>
    </main>
  );
}
