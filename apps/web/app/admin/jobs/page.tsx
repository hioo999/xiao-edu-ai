"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection, AdminToolbar } from "../components/admin-page-layout";
import { currentSession, listMediaOperations, MediaOperation, retryMediaOperation } from "../../../src/api-client";

const stateLabels: Record<string, string> = { queued: "排队中", running: "生成中", succeeded: "已完成", failed: "失败" };
const kindLabels: Record<string, string> = { image: "图片", video: "视频", music: "音乐", voice: "语音" };

export default function JobsAdminPage() {
  const [jobs, setJobs] = useState<MediaOperation[]>([]);
  const [state, setState] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");

  async function refresh() {
    const session = currentSession();
    if (session) setJobs(await listMediaOperations(session.accessToken, { state: state || undefined, kind: kind || undefined }));
  }

  useEffect(() => { void refresh().catch((error) => setStatus(error instanceof Error ? error.message : "无法读取生成任务。")); }, [state, kind]);
  const jobCounts = { queued: jobs.filter((job) => job.state === "queued").length, running: jobs.filter((job) => job.state === "running").length, failed: jobs.filter((job) => job.state === "failed").length, succeeded: jobs.filter((job) => job.state === "succeeded").length };

  async function retry(job: MediaOperation) {
    const session = currentSession();
    if (!session) return;
    try {
      await retryMediaOperation(session.accessToken, job.jobId);
      setStatus(`任务 ${job.jobId} 已重新排队。`);
      await refresh();
    } catch (error) { setStatus(error instanceof Error ? error.message : "任务重试失败。"); }
  }

  return <AdminShell active="/admin/jobs"><AdminPageLayout eyebrow="GENERATION OPERATIONS" title="生成任务" description="查看机构内图片、视频和音乐任务的队列、进度、失败原因与重试状态。" actions={<button className="admin-button--quiet" type="button" onClick={() => void refresh()}>刷新任务</button>}>
    {status && <div className="admin-feedback" role="status">{status}</div>}
    <div className="job-status-strip"><article><small>排队中</small><strong>{jobCounts.queued}</strong></article><article><small>生成中</small><strong>{jobCounts.running}</strong></article><article className={jobCounts.failed ? "is-warning" : "is-ready"}><small>失败待处理</small><strong>{jobCounts.failed}</strong></article><article className="is-ready"><small>已完成</small><strong>{jobCounts.succeeded}</strong></article></div><AdminSection title="任务队列" description="失败任务可以重新排队；正在处理的任务由媒体 Worker 持续更新。" toolbar={<AdminToolbar><label>状态<select aria-label="任务状态" value={state} onChange={(event) => setState(event.target.value)}><option value="">全部状态</option><option value="queued">排队中</option><option value="running">生成中</option><option value="succeeded">已完成</option><option value="failed">失败</option></select></label><label>类型<select aria-label="任务类型" value={kind} onChange={(event) => setKind(event.target.value)}><option value="">全部类型</option><option value="image">图片</option><option value="video">视频</option><option value="music">音乐</option><option value="voice">语音</option></select></label></AdminToolbar>}>
      <div className="admin-log-table"><div className="admin-log-head"><span>任务</span><span>类型 / 学生</span><span>状态</span><span>进度</span><span>操作</span></div>{jobs.map((job) => <div key={job.jobId}><span>{job.jobId}<small>{job.providerId ? ` · ${job.providerId}` : ""}</small></span><span>{kindLabels[job.kind] ?? job.kind}<small> · {job.ownerUserId}</small></span><span className={job.state === "failed" ? "log-warning" : job.state === "succeeded" ? "log-success" : ""}>{stateLabels[job.state] ?? job.state}{job.error && <small title={job.error}> · {job.error}</small>}</span><span>{job.progress}%<small> · {job.attempts} 次</small></span><span>{job.state === "failed" && <button type="button" onClick={() => void retry(job)}>重新排队</button>}{job.assetId && <a href={`/works/${encodeURIComponent(job.assetId)}`}>查看作品</a>}</span></div>)}{jobs.length === 0 && <div><span>暂无生成任务</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}</div>
    </AdminSection>
  </AdminPageLayout></AdminShell>;
}
