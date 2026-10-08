"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { currentSession, listPromptPolishPolicies, PromptPolishPolicy, savePromptPolishPolicy } from "../../../src/api-client";

export default function PromptPolishAdminPage() {
  const [policies, setPolicies] = useState<PromptPolishPolicy[]>([]);
  const [status, setStatus] = useState("正在加载默认润色策略…");

  async function refresh() {
    const session = currentSession();
    if (!session) return;
    setPolicies(await listPromptPolishPolicies(session.accessToken));
    setStatus("");
  }
  useEffect(() => { void refresh().catch(() => setStatus("无法读取润色策略，请确认管理员登录状态。")); }, []);
  async function save(policy: PromptPolishPolicy) {
    const session = currentSession();
    if (!session) return;
    try { await savePromptPolishPolicy(session.accessToken, policy.capability, policy); await refresh(); setStatus(`${policy.name}已保存，学生端会立即使用新策略。`); }
    catch { setStatus("保存失败，请检查提示词内容。"); }
  }
  return <AdminShell active="/admin/polish"><main className="admin-page"><div className="admin-page-heading"><div><p className="admin-eyebrow">PROMPT POLISHING</p><h1>提示词润色策略</h1><p>为不同创作小屋配置不同的儿童友好润色规则。学生只看到“帮我润色”，不会看到系统提示词。</p></div></div>{status && <div className="admin-feedback">{status}</div>}<section className="admin-panel"><div className="admin-panel-heading"><div><h2>已预置 5 套样本提示词</h2><p>可直接编辑、停用或恢复为符合课堂教学方式的内容。请保留 <code>{"{input}"}</code> 作为学生原文插入位置。</p></div></div><div className="polish-policy-list">{policies.map((policy) => <article key={policy.capability} className="polish-policy-card"><div><h2>{policy.name}</h2><span>{policy.capability}</span></div><label>润色系统提示词<textarea value={policy.instruction} onChange={(event) => setPolicies((items) => items.map((item) => item.capability === policy.capability ? { ...item, instruction: event.target.value } : item))} rows={7} /></label><label className="polish-policy-card__toggle"><input type="checkbox" checked={policy.enabled} onChange={(event) => setPolicies((items) => items.map((item) => item.capability === policy.capability ? { ...item, enabled: event.target.checked } : item))} /> 学生端启用此策略</label><button type="button" className="admin-primary-button" onClick={() => void save(policy)}>保存{policy.name}</button></article>)}</div></section></main></AdminShell>;
}
