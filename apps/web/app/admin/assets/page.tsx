"use client";

import { useEffect, useRef, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { CreativeWork, currentSession, deleteWork, listReviewWorks, listStudents, ManagedStudent, listWorkDeployments, publishWorkDeployment, reviewWork, uploadExternalWork, WorkDeployment } from "../../../src/api-client";

export default function AssetsAdminPage() {
  const [works, setWorks] = useState<CreativeWork[]>([]);
  const [status, setStatus] = useState("");
  const [filter, setFilter] = useState("all");
  const [uploadTitle, setUploadTitle] = useState("");
  const [targetStudentId, setTargetStudentId] = useState("");
  const [students, setStudents] = useState<ManagedStudent[]>([]);
  const [studentQuery, setStudentQuery] = useState("");
  const [uploading, setUploading] = useState(false);
  const [publishExample, setPublishExample] = useState(false);
  const [deployments, setDeployments] = useState<WorkDeployment[]>([]);
  const [publishUrls, setPublishUrls] = useState<Record<string, string>>({});
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    const session = currentSession();
    if (!session) return;
    const nextWorks = await listReviewWorks(session.accessToken);
    setWorks(nextWorks);
    const records = await Promise.all(nextWorks.filter((work) => work.kind === "webpage").map(async (work) => {
      try { return await listWorkDeployments(session.accessToken, work.assetId); } catch { return []; }
    }));
    setDeployments(records.flat());
  };

  useEffect(() => { void refresh().catch((error) => setStatus(error instanceof Error ? error.message : "无法读取作品资源。")); }, []);
  useEffect(() => {
    const session = currentSession();
    if (!session) return;
    void listStudents(session.accessToken, session.organizationId, { enabled: true, limit: 100 }).then(setStudents).catch(() => setStudents([]));
  }, []);

  async function remove(work: CreativeWork) {
    const session = currentSession();
    if (!session || !window.confirm(`确定删除作品“${work.title}”吗？此操作不能撤销。`)) return;
    try {
      await deleteWork(session.accessToken, work.assetId);
      await refresh();
      setStatus("作品资源已删除。");
    } catch { setStatus("删除失败，请确认管理员权限。"); }
  }

  async function upload() {
    const session = currentSession();
    const files = Array.from(fileInput.current?.files ?? []);
    if (!session || files.length === 0) return setStatus("请先选择一个 .html 文件或 .zip 网站工程包。");
    setUploading(true);
    try {
      let done = 0;
      const prepared: WorkDeployment[] = [];
      for (const file of files) {
        const result = await uploadExternalWork(session.accessToken, file, uploadTitle, targetStudentId);
        if (publishExample && !targetStudentId) await reviewWork(session.accessToken, result.assetId, "approved", true);
        if (result.deployment) prepared.push(result.deployment);
        done += 1;
      }
      setDeployments((current) => [...prepared, ...current]);
      setStatus(`${done} 件${targetStudentId ? "学生作品" : "教师示例作品"}已导入${publishExample && !targetStudentId ? "并已精选上架到作品墙。" : "，管理员审核通过后即可展示和分享。"}`);
      setUploadTitle("");
      if (fileInput.current) fileInput.current.value = "";
      await refresh();
    } catch (error) { setStatus(error instanceof Error ? error.message : "作品导入失败。"); }
    finally { setUploading(false); }
  }

  async function publishDeployment(deployment: WorkDeployment) {
    const session = currentSession();
    const previewUrl = (publishUrls[deployment.deploymentId] ?? deployment.publishedUrl).trim();
    if (!session || !previewUrl) return setStatus("请先填写已部署网站的 HTTPS 访问地址。");
    try {
      const result = await publishWorkDeployment(session.accessToken, deployment.assetId, deployment.deploymentId, previewUrl);
      setDeployments((items) => items.map((item) => item.deploymentId === deployment.deploymentId ? result.deployment : item));
      setWorks((items) => items.map((work) => work.assetId === result.work.assetId ? result.work : work));
      setStatus("部署地址已登记，作品详情可安全预览该网站。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "部署地址保存失败。请确认是 HTTPS 地址。"); }
  }

  const visibleStudents = students.filter((student) => !studentQuery.trim() || student.username.includes(studentQuery.trim()) || student.userId.includes(studentQuery.trim())).slice(0, 50);
  const visibleWorks = filter === "all" ? works : works.filter((work) => work.kind === filter);
  const visibleDeployments = deployments.filter((deployment) => works.some((work) => work.assetId === deployment.assetId) || !works.length).slice(0, 30);

  return (
    <AdminShell active="/admin/assets">
      <main className="admin-page">
        <div className="admin-page-heading"><div><p className="admin-eyebrow">FILES & ASSETS</p><h1>文件与资源</h1><p>查看、筛选和清理学生生成的图片、视频、音乐与网页作品；课件资源在课程管理中上传。</p></div><a className="admin-primary-button" href="/admin/courses">上传课件</a></div>
        <section className="admin-panel provider-log"><div className="admin-panel-heading"><div><h2>导入外部作品</h2><p>可作为教师示例作品，或填写学生账号 ID 后导入到指定学生的“我的作品”。单个静态网页上传 <code>.html</code>；含数据库、后端的 Web 项目上传 <code>.zip</code> 工程包。工程包仅保存和下载，不会在平台服务器直接执行。</p></div></div><div className="settings-form"><label>作品名称（可选）<input value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} placeholder="例如：太阳系探索网站" /></label><label>归属学生（可选，可搜索选择）<input value={studentQuery} onChange={(event) => setStudentQuery(event.target.value)} placeholder="输入学生账号或用户 ID 搜索" /><select value={targetStudentId} onChange={(event) => setTargetStudentId(event.target.value)}><option value="">不归属：作为教师示例作品</option>{visibleStudents.map((student) => <option key={student.userId} value={student.userId}>{student.username} · {student.classId ?? "未分班"}</option>)}</select></label><label className="api-editor__switches"><input type="checkbox" checked={publishExample} disabled={Boolean(targetStudentId)} onChange={(event) => setPublishExample(event.target.checked)} /> 作为教师示例：导入后直接精选上架到学生作品墙</label><label>选择文件（可多选）<input ref={fileInput} type="file" multiple accept=".html,.htm,.zip,text/html,application/zip" /></label><button type="button" className="admin-primary-button" disabled={uploading} onClick={() => void upload()}>{uploading ? "正在上传…" : "导入作品审核库"}</button></div></section>
        {visibleDeployments.length > 0 && <section className="admin-panel provider-log"><div className="admin-panel-heading"><div><h2>工程部署与预览</h2><p>ZIP 包只做安全保存和解析，不在本平台服务器执行。请先在独立沙箱或云服务部署，再登记 HTTPS 预览地址。</p></div></div><div className="admin-log-table"><div className="admin-log-head"><span>作品</span><span>工程类型</span><span>依赖</span><span>环境变量模板</span><span>数据库</span><span>发布</span></div>{visibleDeployments.map((deployment) => <div key={deployment.deploymentId}><span>{works.find((work) => work.assetId === deployment.assetId)?.title ?? deployment.assetId}</span><span>{deployment.projectType}</span><span>{deployment.manifest.dependencies.length} 项</span><span>{Object.keys(deployment.envTemplate).slice(0, 3).join(", ") || "—"}</span><span>{deployment.manifest.hasDatabaseHint ? "需要" : "无"}</span><span><small>{deployment.state === "published" ? "已发布" : "待登记"}</small><input aria-label={`${deployment.deploymentId} HTTPS 预览地址`} value={publishUrls[deployment.deploymentId] ?? deployment.publishedUrl} onChange={(event) => setPublishUrls((current) => ({ ...current, [deployment.deploymentId]: event.target.value }))} placeholder="https://example.com" /><button type="button" onClick={() => void publishDeployment(deployment)}>{deployment.state === "published" ? "更新地址" : "登记发布"}</button></span></div>)}</div></section>}
        <section className="admin-panel provider-log"><div className="admin-panel-heading"><div><h2>学生创作资源</h2><p>作品可在展示墙审核和精选；删除仅用于违规、重复或失效资源。</p></div><label>类型筛选<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">全部类型</option><option value="webpage">网页</option><option value="image">图片</option><option value="music">音乐</option><option value="video">视频</option><option value="text">文字</option></select></label></div>{status && <div className="admin-feedback">{status}</div>}<div className="admin-log-table"><div className="admin-log-head"><span>作品</span><span>类型</span><span>学生</span><span>审核</span><span>操作</span></div>{visibleWorks.map((work) => <div key={work.assetId}><span>{work.title}</span><span>{work.kind}</span><span>{work.ownerUserId}</span><span>{work.reviewState}{work.featured ? " · 精选" : ""}</span><span><a href="/admin/showcase">审核</a><button type="button" onClick={() => void remove(work)}>删除</button></span></div>)}</div></section>
      </main>
    </AdminShell>
  );
}
