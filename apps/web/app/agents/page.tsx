"use client";

import { Bot, Plus, Save, Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { currentSession, deleteStudentAgent, listStudentAgents, saveStudentAgent, type SelectableTextModel, type StudentAgentDraft, type StudentAgentProfile } from "../../src/api-client";
import { creationRequest, defaultAgentSettings, listAgentConversations, type AgentSettings, type AgentConversation, type AgentMessage, type AgentOptions } from "../../src/creation-api";
import { CreationHeader } from "../components/creation-header";
import { AgentResult } from "./agent-result";
import "./student-agent.css";

const initialDraft: StudentAgentDraft = { name: "我的创作小助手", description: "把奇妙想法变成清楚、有趣的作品。", category: "通用", instructions: "你是一位耐心、友善的小学 AI 学习伙伴。请用适合 3-6 年级学生的中文回答：先给清楚的结果，再用短步骤说明。遇到不适合儿童的内容，要温和地提醒并引导到安全的创作方向。", providerId: "" };
const categories = ["通用", "故事写作", "绘画灵感", "网页策划", "学习辅导"];
const templates: { name: string; capability: AgentSettings["capability"]; instruction: string }[] = [
  { name: "故事精灵", capability: "text", instruction: "你是童话作家。根据我的主题直接写出适合小学生的短故事，有标题、开头、转折和温暖的结尾。" },
  { name: "网页魔法师", capability: "html", instruction: "你是网页创作老师。把我的描述做成能直接试玩的单文件网页，按钮大、配色活泼，保持原来的主题和互动。" },
  { name: "神笔画家", capability: "image", instruction: "你是儿童绘本画家。把我的主题变成画面，补充主角、动作、环境和温暖的颜色。" },
  { name: "音乐伙伴", capability: "music", instruction: "你是儿歌创作伙伴。用我的主题写一首能演唱的儿歌，有主歌和重复的副歌，押韵、积极、好记。" },
];
const emptyOptions: AgentOptions = { skills: [], mcp: [], knowledge: [], runtimes: ["gateway"], models: [] };

export default function AgentsPage() {
  const [draft, setDraft] = useState<StudentAgentDraft>(initialDraft);
  const [profiles, setProfiles] = useState<StudentAgentProfile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [models, setModels] = useState<SelectableTextModel[]>([]);
  const [options, setOptions] = useState<AgentOptions>(emptyOptions);
  const [settings, setSettings] = useState<AgentSettings>(defaultAgentSettings);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [conversations, setConversations] = useState<AgentConversation[]>([]);
  const [conversationId, setConversationId] = useState("");
  const [task, setTask] = useState("");
  const [status, setStatus] = useState("写好指令，再在右侧发送一个问题试试。");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const previewRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const session = currentSession();
    if (!session) { setStatus("请用老师分配的平台学生账号登录。"); return; }
    setSignedIn(true);
    setBusy(true);
    void Promise.all([creationRequest<AgentOptions>(session.accessToken, "/student-agents/options"), listStudentAgents(session.accessToken)]).then(async ([available, saved]) => {
      setOptions(available); setModels(available.models); setProfiles(saved);
      if (saved.length) await choose(saved[0]);
      else setDraft((current) => ({ ...current, providerId: available.models[0]?.providerId ?? "" }));
      setStatus(available.models.length ? "已准备好，可以编辑指令或开始对话。" : "老师还没有开启可用的文字模型。");
    }).catch((error) => setStatus(error instanceof Error ? error.message : "智能体暂时无法加载。")).finally(() => setBusy(false));
  }, []);

  function edit<K extends keyof StudentAgentDraft>(field: K, value: StudentAgentDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  async function choose(profile: StudentAgentProfile) {
    const session = currentSession(); if (!session) return;
    setBusy(true);
    try {
      const [configuration, saved] = await Promise.all([creationRequest<AgentSettings>(session.accessToken, "/student-agents/" + profile.agentId + "/settings"), listAgentConversations(session.accessToken, profile.agentId)]);
      setSelectedId(profile.agentId);
      setDraft({ name: profile.name, description: profile.description, category: profile.category, instructions: profile.instructions, providerId: profile.providerId });
      setSettings(configuration); setConversations(saved); setConversationId(saved[0]?.sessionId ?? ""); setMessages(saved[0]?.messages ?? []); setTask("");
      setStatus("已打开「" + profile.name + "」，历史对话已恢复。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "无法打开智能体。"); }
    finally { setBusy(false); }
  }

  function createNew() {
    setSelectedId(""); setDraft({ ...initialDraft, providerId: models[0]?.providerId ?? "" }); setSettings(defaultAgentSettings);
    setMessages([]); setConversations([]); setConversationId(""); setTask(""); setStatus("填写指令后保存，或者直接开始试聊。");
  }

  async function persist() {
    const session = currentSession();
    if (!session) throw new Error("请先登录平台学生账号。");
    if (!draft.name.trim() || !draft.instructions.trim() || !draft.providerId) throw new Error("名称、指令和模型都必须填写。");
    const profile = await saveStudentAgent(session.accessToken, draft, selectedId || undefined);
    setSelectedId(profile.agentId);
    await creationRequest(session.accessToken, "/student-agents/" + profile.agentId + "/settings", "PUT", settings);
    setProfiles((current) => [...current.filter((item) => item.agentId !== profile.agentId), profile]);
    setSelectedId(profile.agentId);
    return profile;
  }

  async function save() {
    setBusy(true);
    try { await persist(); setStatus("智能体设置已保存，下次登录还可以继续使用。"); }
    catch (error) { setStatus(error instanceof Error ? error.message : "保存失败，请重试。"); }
    finally { setBusy(false); }
  }

  async function remove() {
    const session = currentSession(); if (!session || !selectedId) return;
    setBusy(true);
    try { await deleteStudentAgent(session.accessToken, selectedId); setProfiles((current) => current.filter((profile) => profile.agentId !== selectedId)); createNew(); setStatus("智能体已删除，作品夹里的回答仍保留。"); }
    catch (error) { setStatus(error instanceof Error ? error.message : "删除没有完成。"); }
    finally { setBusy(false); }
  }

  async function newConversation() {
    const session = currentSession(); if (!session) return;
    setBusy(true);
    try {
      const profile = await persist();
      const created = await creationRequest<AgentConversation>(session.accessToken, "/student-agents/" + profile.agentId + "/sessions", "POST", {});
      setConversations((current) => [created, ...current]); setConversationId(created.sessionId); setMessages([]); setStatus("新对话已准备好，以前的对话可以在下拉框中找回。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "无法新建对话。"); }
    finally { setBusy(false); }
  }

  async function send() {
    const session = currentSession(); const question = task.trim();
    if (!session) { setStatus("请先登录平台学生账号。"); return; }
    if (!question || busy) return;
    setBusy(true); setStatus("正在按照你的指令创作…");
    try {
      const profile = await persist();
      let selectedConversation = conversationId;
      if (!selectedConversation) selectedConversation = (await creationRequest<AgentConversation>(session.accessToken, "/student-agents/" + profile.agentId + "/sessions", "POST", {})).sessionId;
      setConversationId(selectedConversation);
      const result = await creationRequest<{ conversation: AgentConversation }>(session.accessToken, "/student-agents/sessions/" + selectedConversation + "/messages", "POST", { text: question });
      setMessages(result.conversation.messages); setConversations((current) => [result.conversation, ...current.filter((item) => item.sessionId !== result.conversation.sessionId)]); setTask(""); setStatus("创作结果和对话已保存。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "这次没有完成，可以保留输入重新尝试。"); }
    finally { setBusy(false); }
  }

  function toggle(field: "skillIds" | "mcpIds" | "knowledgeIds", id: string) {
    setSettings((current) => ({ ...current, [field]: current[field].includes(id) ? current[field].filter((value) => value !== id) : [...current[field], id] }));
  }

  return <main className="student-agent-page creation-surface">
    <CreationHeader title="创建我的智能体" description="设置身份和指令，选择模型，再和自己的学习伙伴对话。" active="/agents"><button type="button" onClick={() => previewRef.current?.scrollIntoView({ behavior: "smooth" })}>去试聊 →</button></CreationHeader>
    <div className="student-agent-layout">
      <section className="student-agent-editor" aria-label="智能体设置">
        <div className="student-agent-editor__top"><label>我的智能体<select aria-label="选择已保存智能体" disabled={busy} value={selectedId} onChange={(event) => { const profile = profiles.find((item) => item.agentId === event.target.value); if (profile) void choose(profile); else createNew(); }}><option value="">新智能体</option>{profiles.map((profile) => <option key={profile.agentId} value={profile.agentId}>{profile.name}</option>)}</select></label><button type="button" disabled={busy} onClick={createNew}><Plus size={16} /> 新建</button></div>
        <div className="agent-template-list" aria-label="智能体灵感模板">{templates.map((template) => <button type="button" disabled={busy} key={template.name} onClick={() => { setDraft((current) => ({ ...current, name: template.name, instructions: template.instruction })); setSettings((current) => ({ ...current, capability: template.capability })); }}>{template.name}</button>)}</div>
        <label>名称 *<input disabled={busy} value={draft.name} maxLength={40} onChange={(event) => edit("name", event.target.value)} placeholder="例如：月球故事向导" /></label>
        <label>指令 *<textarea disabled={busy} className="student-agent-instructions" value={draft.instructions} maxLength={3000} onChange={(event) => edit("instructions", event.target.value)} placeholder="告诉它身份、回答方式和规则。" rows={6} /><small>每次创作都会使用这里的指令，并延续当前对话。</small></label>
        <label>模型 *<select disabled={busy} aria-label="选择大模型" value={draft.providerId} onChange={(event) => edit("providerId", event.target.value)}><option value="">请选择老师开启的模型</option>{models.map((model) => <option key={model.providerId} value={model.providerId}>{model.name} · {model.providerKind}</option>)}</select></label>
        <details className="student-agent-tools"><summary>描述与分类</summary><label>描述<textarea disabled={busy} value={draft.description} maxLength={180} onChange={(event) => edit("description", event.target.value)} placeholder="它擅长帮助同学做什么？" rows={2} /></label><label>类别<select disabled={busy} value={draft.category} onChange={(event) => edit("category", event.target.value)}>{categories.map((category) => <option key={category}>{category}</option>)}</select></label></details>
        <label>输出类型<select aria-label="输出类型" disabled={busy} value={settings.capability} onChange={(event) => setSettings((current) => ({ ...current, capability: event.target.value as AgentSettings["capability"] }))}><option value="text">文字回答</option><option value="html">网页与小游戏</option><option value="image">图片作品</option><option value="music">歌词与歌曲</option><option value="video">视频作品</option></select><small>图片、歌曲和视频使用老师在后台开启的对应能力，视频时长由老师设定。</small></label>
        {options.runtimes.length > 1 && <label>智能体模式<select disabled={busy} value={settings.runtime} onChange={(event) => setSettings((current) => ({ ...current, runtime: event.target.value as AgentSettings["runtime"] }))}><option value="gateway">标准模式</option><option value="agentscope">工具推理模式</option></select></label>}
        <details className="student-agent-tools"><summary>教学规则、工具与知识资料</summary>{([["skills", "skillIds", "教学规则"], ["mcp", "mcpIds", "老师授权的工具"], ["knowledge", "knowledgeIds", "知识资料"]] as const).map(([group, field, label]) => <div key={group}><h3>{label}</h3>{options[group].length ? options[group].map((option) => <label key={option.id}><input type="checkbox" disabled={busy} checked={settings[field].includes(option.id)} onChange={() => toggle(field, option.id)} />{option.name}</label>) : <small>老师还没有上架可用的{label}。</small>}</div>)}</details>
        {!signedIn && <p className="student-agent-editor__note"><a href="/login?next=%2Fagents">使用平台学生账号登录 →</a></p>}
        <div className="student-agent-editor__actions"><button type="button" disabled={busy || !signedIn} onClick={() => void save()}><Save size={16} /> 保存设置</button>{selectedId && <button type="button" className="student-agent-delete" disabled={busy} onClick={() => void remove()}><Trash2 size={16} /> 删除</button>}</div>
      </section>
      <section ref={previewRef} className="student-agent-preview" aria-label="智能体对话测试">
        <div className="student-agent-preview__head"><div className="student-agent-preview__icon"><Sparkles size={22} /></div><div><h2>{draft.name.trim() || "未命名智能体"}</h2><p>{draft.description.trim() || "写下描述，介绍你的智能体。"}</p></div><span>{models.find((model) => model.providerId === draft.providerId)?.name || "未选模型"}</span></div>
        <div className="agent-sessions"><select aria-label="历史对话" disabled={busy} value={conversationId} onChange={(event) => { const selected = conversations.find((item) => item.sessionId === event.target.value); if (selected) { setConversationId(selected.sessionId); setMessages(selected.messages); } }}><option value="">选择历史对话</option>{conversations.map((conversation) => <option key={conversation.sessionId} value={conversation.sessionId}>{conversation.title}</option>)}</select><button type="button" disabled={busy || !signedIn} onClick={() => void newConversation()}>＋ 新对话</button></div>
        <div className="student-agent-chat" aria-live="polite">{messages.length === 0 ? <div className="student-agent-welcome"><Bot size={38} /><h3>先问我一个问题吧！</h3><p>试试：“帮我想一个关于月球花园的故事。”</p></div> : messages.map((message, index) => <div className={"student-agent-message student-agent-message--" + message.role} key={index}><b>{message.role === "student" ? "我" : draft.name || "智能体"}</b>{message.role === "assistant" ? <AgentResult message={message} name={draft.name} onStatus={setStatus} /> : <p>{message.text}</p>}</div>)}</div>
        <div className="student-agent-composer"><p role="status">{status}</p><label>测试问题<textarea disabled={busy} aria-label="测试问题" value={task} maxLength={1000} onChange={(event) => setTask(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} placeholder={"发送消息给 " + (draft.name || "我的智能体")} rows={3} /></label><button type="button" disabled={busy || !task.trim() || !signedIn} onClick={() => void send()}><Send size={17} /> {busy ? "回答中…" : "发送"}</button></div>
      </section>
    </div>
  </main>;
}
