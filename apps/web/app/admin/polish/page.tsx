"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import { currentSession, listPromptPolishPolicies, PromptPolishPolicy, resetPromptPolishPolicy, savePromptPolishPolicy } from "../../../src/api-client";

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
  async function reset(policy: PromptPolishPolicy) {
    const session = currentSession();
    if (!session) return;
    try { await resetPromptPolishPolicy(session.accessToken, policy.capability); await refresh(); setStatus(`${policy.name}已恢复为课堂推荐样本。`); }
    catch { setStatus("恢复默认策略失败，请稍后再试。"); }
  }
  return <AdminShell active="/admin/polish"><AdminPageLayout eyebrow="PROMPT POLISHING" title="提示词润色策略" description="为不同创作小屋配置儿童友好的润色规则。学生只看到“帮我润色”，不会看到系统提示词。">{status && <div className="admin-feedback" role="status">{status}</div>}<AdminSection title="课堂润色规则" description={'已预置 5 套样本提示词。请保留 {input} 作为学生原文插入位置。每张卡片独立保存，修改后立即影响学生端。'}><div className="polish-policy-list">{policies.map((policy) => <article key={policy.capability} className="polish-policy-card"><header className="polish-policy-card__header"><div><p className="admin-eyebrow">{policy.capability.toUpperCase()}</p><h2>{policy.name}</h2></div><span className={policy.enabled ? "is-enabled" : ""}>{policy.enabled ? "已启用" : "已停用"}</span></header><label className="polish-policy-card__field"><span>润色系统提示词</span><small>告诉模型如何处理学生输入，支持多段文字和换行。</small><textarea aria-label={`${policy.name}润色系统提示词`} value={policy.instruction} onChange={(event) => setPolicies((items) => items.map((item) => item.capability === policy.capability ? { ...item, instruction: event.target.value } : item))} rows={12} /></label><label className="polish-policy-card__toggle"><input type="checkbox" checked={policy.enabled} onChange={(event) => setPolicies((items) => items.map((item) => item.capability === policy.capability ? { ...item, enabled: event.target.checked } : item))} /> 学生端启用此策略</label><div className="admin-inline-actions"><button type="button" className="admin-primary-button" onClick={() => void save(policy)}>保存{policy.name}</button><button type="button" className="admin-secondary-button" onClick={() => void reset(policy)}>恢复默认样本</button></div></article>)}</div></AdminSection></AdminPageLayout></AdminShell>;
}
