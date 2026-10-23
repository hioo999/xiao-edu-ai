"use client";

import { useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import {
  agentReadiness,
  AgentReadiness,
  currentSession,
  DeadLetterJob,
  listDeadLetters,
  listMediaOperations,
  MediaOperation,
  mediaWorkerReadiness,
  platformReadiness,
  retryDeadLetter,
} from "../../../src/api-client";

export default function OperationsAdminPage() {
  const [storage, setStorage] = useState("正在检查…");
  const [agents, setAgents] = useState("正在检查…");
  const [agentChecks, setAgentChecks] = useState<AgentReadiness["checks"]>([]);
  const [worker, setWorker] = useState("正在检查…");
  const [jobs, setJobs] = useState<MediaOperation[]>([]);
  const [deadLetters, setDeadLetters] = useState<DeadLetterJob[]>([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    const session = currentSession();
    void platformReadiness().then((ready) => setStorage(ready.storage === "ok" ? "正常" : ready.storage)).catch(() => setStorage("异常"));
    void agentReadiness().then((ready) => {
      setAgents(ready.mode === "gateway" ? "Gateway 模式（可用）" : ready.ready ? "AgentScope 已就绪" : ready.reason);
      setAgentChecks(ready.checks);
    }).catch(() => { setAgents("未配置"); setAgentChecks([]); });
    void mediaWorkerReadiness().then((ready) => setWorker(ready.workerReady ? "运行中" : ready.reason ?? "未运行")).catch(() => setWorker("未配置"));
    if (session) {
      try { setJobs(await listMediaOperations(session.accessToken, {})); } catch { setJobs([]); }
      try { setDeadLetters(await listDeadLetters(session.accessToken)); } catch { setDeadLetters([]); }
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function retry(jobId: string) {
    const session = currentSession();
    if (!session) return setStatus("请先登录管理员账号。");
    try {
      await retryDeadLetter(session.accessToken, jobId);
      setStatus(`任务 ${jobId} 已重新入队。`);
      await refresh();
    } catch {
      setStatus("重试失败任务失败。");
    }
  }

  return (
    <AdminShell active="/admin/operations">
      <AdminPageLayout eyebrow="PLATFORM OPERATIONS" title="系统运维" description="查看存储、智能体运行时、生成队列和失败任务重试状态。" actions={<button className="admin-primary-button" type="button" onClick={() => void refresh()}>刷新状态</button>}>

        <AdminSection title="运行保障" description="生产环境依赖 SQLite 数据卷与外部 AI 服务。" toolbar={<span className="status-chip status-chip--good">● 每日备份已启用</span>}>
          <div className="settings-note">存储状态：{storage} · 智能体运行时：{agents} · 生成队列：{worker}</div>
          {agentChecks.length > 0 && <div className="admin-log-table"><div className="admin-log-head"><span>AgentScope 预检项</span><span>状态</span><span>说明</span></div>{agentChecks.map((check) => <div key={check.id}><span>{check.id}</span><span className={check.ready ? "log-success" : "log-warning"}>{check.ready ? "已就绪" : "待配置"}</span><span>{check.detail}</span></div>)}</div>}
          {status && <div className="admin-feedback">{status}</div>}
        </AdminSection>

        <AdminSection title="生成任务" description="查看机构内图片、音乐、视频生成任务的最新状态。">
          <div className="admin-log-table"><div className="admin-log-head"><span>任务</span><span>类型</span><span>状态</span><span>进度</span><span>失败信息</span></div>{jobs.length ? jobs.map((job) => <div key={job.jobId}><span>{job.jobId}</span><span>{job.kind}</span><span>{job.state}</span><span>{job.progress}</span><span>{job.error ?? "—"}</span></div>) : <div><span>暂无生成任务</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}</div>
        </AdminSection>

        <AdminSection title="失败任务重试" description="Redis 队列启用后，可在此查看并重试进入死信队列的任务。">
          <div className="admin-log-table"><div className="admin-log-head"><span>任务</span><span>类型</span><span>状态</span><span>失败信息</span><span>操作</span></div>{deadLetters.length ? deadLetters.map((job) => <div key={job.jobId}><span>{job.jobId}</span><span>{job.kind}</span><span>{job.state}</span><span>{job.error ?? "—"}</span><span><button type="button" onClick={() => void retry(job.jobId)}>重试</button></span></div>) : <div><span>暂无死信任务</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}</div>
        </AdminSection>
      </AdminPageLayout>
    </AdminShell>
  );
}
