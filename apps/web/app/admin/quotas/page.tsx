"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { currentSession, modelCallSummary, setUsageLimit, UsageMetric, usageSummary } from "../../../src/api-client";

const metricLabels: Record<string, string> = { text: "文字生成", image: "图片生成", video: "视频生成", music: "音乐生成", storage: "资源存储" };
const scopes = [{ id: "organization", label: "机构" }, { id: "class", label: "班级" }, { id: "student", label: "学生" }, { id: "platform", label: "平台" }];

export default function QuotasAdminPage() {
  const [metrics, setMetrics] = useState<UsageMetric[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({ text: "10000", image: "1000", video: "200", music: "500", storage: "100" });
  const [calls, setCalls] = useState<{ providerId: string; capability: string; outcome: string; count: number }[]>([]);
  const [scope, setScope] = useState("organization");
  const [scopeId, setScopeId] = useState("");
  const [message, setMessage] = useState("");
  const session = typeof window === "undefined" ? null : currentSession();
  const isPlatformAdmin = session?.role === "platform_admin";

  const refresh = async () => {
    const activeSession = currentSession();
    if (!activeSession) return;
    const effectiveScopeId = scope === "organization" ? undefined : scopeId.trim() || undefined;
    const [nextMetrics, nextCalls] = await Promise.all([usageSummary(activeSession.accessToken, scope, effectiveScopeId), modelCallSummary(activeSession.accessToken)]);
    setMetrics(nextMetrics); setCalls(nextCalls);
    setDrafts((current) => ({ ...current, ...Object.fromEntries(nextMetrics.map((metric) => [metric.metric, String(metric.limit)])) }));
  };

  useEffect(() => { void refresh().catch(() => setMessage("暂无可读取的额度或调用数据。")); }, [scope, scopeId]);
  async function save(metric: "text" | "image" | "video" | "music" | "storage") {
    const activeSession = currentSession(); const limit = Number(drafts[metric]); const effectiveScopeId = scope === "organization" ? undefined : scopeId.trim() || undefined;
    if (!activeSession || !Number.isInteger(limit) || limit < 0) return setMessage("额度必须是大于或等于 0 的整数。");
    if (scope !== "organization" && !effectiveScopeId) return setMessage("请填写班级、学生或平台范围标识。");
    try { await setUsageLimit(activeSession.accessToken, metric, limit, scope, effectiveScopeId); await refresh(); setMessage(`${metricLabels[metric]}额度已保存。`); } catch { setMessage("额度保存失败；机构管理员只能调整本机构的机构级额度。"); }
  }
  const allMetrics = ["text", "image", "video", "music", "storage"] as const;
  const metricMap = new Map(metrics.map((metric) => [metric.metric, metric]));
  const availableScopes = isPlatformAdmin ? scopes : scopes.slice(0, 1);
  return <AdminShell active="/admin/quotas"><main className="admin-page"><div className="admin-page-heading"><div><p className="admin-eyebrow">USAGE & COST CENTER</p><h1>额度与调用日志</h1><p>可按机构、班级或学生配置额度；非平台管理员仅能管理本机构的总额度。</p></div></div>{message && <div className="admin-feedback">{message}</div>}<section className="admin-panel"><div className="admin-panel-heading"><div><h2>额度范围</h2><p>配置为 0 即关闭对应范围的创作能力。</p></div><span><select value={scope} onChange={(event) => { setScope(event.target.value); setScopeId(""); }}>{availableScopes.map((item) => <option key={item.id} value={item.id}>{item.label}级</option>)}</select>{scope !== "organization" && <input value={scopeId} onChange={(event) => setScopeId(event.target.value)} placeholder="范围标识，例如 class-3-2" />}</span></div><div className="admin-log-table"><div className="admin-log-head"><span>能力</span><span>额度上限</span><span>已使用</span><span>任务预留</span><span>操作</span></div>{allMetrics.map((metric) => { const item = metricMap.get(metric); return <div key={metric}><span>{metricLabels[metric]}</span><span><input aria-label={`${metric} limit`} type="number" min="0" value={drafts[metric] ?? ""} onChange={(event) => setDrafts((value) => ({ ...value, [metric]: event.target.value }))} /></span><span>{item?.used ?? 0}</span><span>{item?.reserved ?? 0}</span><span><button type="button" onClick={() => void save(metric)}>保存</button><small>剩余 {Math.max(0, Number(drafts[metric] ?? 0) - (item?.used ?? 0) - (item?.reserved ?? 0))}</small></span></div>; })}</div></section><section className="admin-panel provider-log"><div className="admin-panel-heading"><h2>模型调用汇总</h2></div><div className="admin-log-table"><div className="admin-log-head"><span>模型配置</span><span>能力</span><span>结果</span><span>次数</span><span /></div>{calls.map((call, index) => <div key={`${call.providerId}-${index}`}><span>{call.providerId}</span><span>{call.capability}</span><span className={call.outcome === "succeeded" ? "log-success" : "log-warning"}>{call.outcome}</span><span>{call.count}</span><span /></div>)}</div></section></main></AdminShell>;
}
