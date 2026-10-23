"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import { currentSession, deleteAgent, listAgents, ManagedAgent, saveAgent } from "../../../src/api-client";

const capabilities: ManagedAgent["capability"][] = ["text", "image", "video", "music", "html"];

export default function AgentsAdminPage() {
  const [agents, setAgents] = useState<ManagedAgent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [name, setName] = useState("");
  const [capability, setCapability] = useState<ManagedAgent["capability"]>("text");
  const [gradeRange, setGradeRange] = useState("3-6");
  const [published, setPublished] = useState(false);
  const [status, setStatus] = useState("");

  const refresh = async () => {
    const session = currentSession();
    if (session) setAgents(await listAgents(session.accessToken));
  };

  useEffect(() => { void refresh().catch((error) => setStatus(error instanceof Error ? error.message : "无法读取智能体。")); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const session = currentSession();
    if (!session) return;
    try {
      await saveAgent(session.accessToken, { agentId: agentId.trim(), name: name.trim(), capability, gradeRange: gradeRange.trim(), published });
      setAgentId(""); setName(""); setCapability("text"); setGradeRange("3-6"); setPublished(false);
      await refresh();
      setStatus("智能体已保存。发布后学生端将自动可见。");
    } catch {
      setStatus("保存失败：标识仅可使用小写字母、数字和连字符。");
    }
  }

  async function toggle(agent: ManagedAgent) {
    const session = currentSession();
    if (!session) return;
    try {
      await saveAgent(session.accessToken, { ...agent, published: !agent.published });
      await refresh();
    } catch { setStatus("更新发布状态失败。"); }
  }

  async function remove(agent: ManagedAgent) {
    const session = currentSession();
    if (!session || !window.confirm(`确定删除“${agent.name}”吗？`)) return;
    try {
      await deleteAgent(session.accessToken, agent.agentId);
      await refresh();
      setStatus("智能体已删除。");
    } catch { setStatus("内置智能体不能删除；自定义智能体可删除。"); }
  }

  return (
    <AdminShell active="/admin/agents">
      <AdminPageLayout eyebrow="AGENTS & TOOLS" title="智能体" description="管理学生可直接选择的 AI 伙伴；Skill、MCP 和知识库在 AI 能力中心分别配置。" actions={<><a href="/admin/skills">管理 Skills</a><a className="admin-button--quiet" href="/admin/mcp">管理 MCP</a></>}>
        <AdminSection title="创建智能体" description="用清晰的能力范围和年级约束，避免学生选择到不适合的模型。">
          <form className="settings-form" onSubmit={submit}>
            <label>智能体标识<input value={agentId} onChange={(event) => setAgentId(event.target.value)} placeholder="story-coach" required /></label>
            <label>名称<input value={name} onChange={(event) => setName(event.target.value)} placeholder="故事小导演" required /></label>
            <label>创作能力<select value={capability} onChange={(event) => setCapability(event.target.value as ManagedAgent["capability"])}>{capabilities.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>适用年级<input value={gradeRange} onChange={(event) => setGradeRange(event.target.value)} placeholder="3-6" required /></label>
            <label>学生端开放<select value={published ? "yes" : "no"} onChange={(event) => setPublished(event.target.value === "yes")}><option value="no">先保存为草稿</option><option value="yes">立即发布</option></select></label>
            <button className="admin-primary-button" type="submit">保存智能体</button>
          </form>
          {status && <div className="admin-feedback">{status}</div>}
        </AdminSection>
        <AdminSection title="AI 伙伴清单" description="学生只会看到已发布的智能体；内置伙伴可启停但不会被删除。">
          <div className="admin-panel-heading"><div><h2>AI 伙伴清单</h2><p>学生只会看到已发布的智能体；内置伙伴可启停但不会被删除。</p></div><a href="/admin/knowledge">知识库 →</a></div>
          <div className="admin-log-table"><div className="admin-log-head"><span>名称</span><span>能力</span><span>适用年级</span><span>状态</span><span>操作</span></div>{agents.map((agent) => <div key={agent.agentId}><span>{agent.name}<small> · {agent.agentId}</small></span><span>{agent.capability}</span><span>{agent.gradeRange} 年级</span><span>{agent.published ? "已发布" : "草稿"}</span><span><button type="button" onClick={() => void toggle(agent)}>{agent.published ? "下线" : "发布"}</button><button type="button" onClick={() => void remove(agent)}>删除</button></span></div>)}</div>
        </AdminSection>
      </AdminPageLayout>
    </AdminShell>
  );
}
