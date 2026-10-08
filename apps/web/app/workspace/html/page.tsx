"use client";

import { useEffect, useMemo, useState } from "react";
import { currentSession, generateHtml, polishPrompt } from "../../../src/api-client";

const demoHtml = `<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;font-family:system-ui;background:linear-gradient(135deg,#082f49,#164e63);color:white;min-height:100vh;display:grid;place-items:center">
    <main style="text-align:center;padding:48px"><p style="letter-spacing:.2em;color:#67e8f9">MY FIRST WEBPAGE</p><h1>我的太空探险</h1><p id="message">点击按钮，开始探索星球。</p><button onclick="document.getElementById('message').textContent='发现一颗会发光的蓝色星球！';this.textContent='继续探索'" style="border:0;border-radius:999px;padding:14px 24px;background:#67e8f9;color:#082f49;cursor:pointer">开始探索</button></main>
  </body>
</html>`;

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

  useEffect(() => {
    const starterPrompt = new URLSearchParams(window.location.search).get("prompt")?.trim() ?? "";
    if (starterPrompt) setPrompt(starterPrompt);
  }, []);

  async function submitPrompt() {
    const value = prompt.trim();
    if (!value) return;
    const session = currentSession();
    if (!session) {
      setMessages((current) => [...current, { role: "assistant", text: "请先登录平台账号后再开始网页创作。" }]);
      return;
    }
    setMessages((current) => [...current, { role: "student", text: value }]);
    setPrompt("");
    try {
      const projectId = `web-${session.userId}`;
      const generated = await generateHtml(session.accessToken, projectId, value);
      setHtml(generated.currentVersion.html);
      setTutorial(generated.currentVersion.teachingSteps);
      setMessages((current) => [...current, { role: "assistant", text: generated.assetId ? "新版本已经生成并自动放进作品夹，等待老师审核。你可以在右侧预览，并查看每一步学习提示。" : "新版本已经生成，可以在右侧预览，并查看每一步学习提示。" }]);
      setActiveTab("preview");
    } catch (error) {
      const message = error instanceof Error ? error.message : "网页创作服务暂时不可用，请稍后再试。";
      setMessages((current) => [...current, { role: "assistant", text: message }]);
    }
  }

  async function polish() {
    const value = prompt.trim();
    const session = currentSession();
    if (!session) return setMessages((current) => [...current, { role: "assistant", text: "请先登录平台账号后再使用润色功能。" }]);
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
    URL.revokeObjectURL(url);
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <a href="/" className="workspace-back">← 创作大厅</a>
        <div><p className="student-home__eyebrow">网页设计 · VIBE CODING</p><h1>网页创作工作台</h1></div>
        <div className="workspace-actions"><a className="workspace-game-link" href="/play">🎮 先试玩小游戏</a><button onClick={() => download("my-webpage.html", html, "text/html")}>下载 HTML</button><button onClick={() => download("teaching-steps.txt", tutorial.join("\n"), "text/plain")}>下载指导</button></div>
      </header>
      <section className="workspace-grid">
        <aside className="chat-panel">
          <div className="panel-heading"><strong>和网页创作伙伴对话</strong><span>不需要打开代码</span></div>
          <div className="chat-messages">
            {messages.map((message, index) => <div className={`chat-bubble chat-bubble--${message.role}`} key={`${message.role}-${index}`}>{message.text}</div>)}
          </div>
          <div className="prompt-box"><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitPrompt(); } }} placeholder="例如：把标题改成海底探险，颜色更明亮" /><button type="button" disabled={polishing} onClick={() => void polish()}>{polishing ? "润色中…" : "✨ 帮我润色"}</button><button onClick={submitPrompt}>发送</button></div>
        </aside>
        <section className="preview-panel">
          <div className="workspace-tabs"><button className={activeTab === "preview" ? "is-active" : ""} onClick={() => setActiveTab("preview")}>预览</button><button className={activeTab === "tutorial" ? "is-active" : ""} onClick={() => setActiveTab("tutorial")}>教程</button></div>
          {activeTab === "preview" ? <iframe title="网页预览" sandbox="allow-scripts" srcDoc={html} className="html-preview" /> : <div className="tutorial-panel"><h2>这一步你学会了什么？</h2>{tutorial.map((step, index) => <div className="tutorial-step" key={step}><span>{index + 1}</span><p>{step}</p></div>)}<p className="tutorial-tip">小提示：你可以继续用自然语言要求修改，不需要打开代码。</p></div>}
        </section>
      </section>
    </main>
  );
}
