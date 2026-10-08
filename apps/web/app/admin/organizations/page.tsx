"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import {
  currentSession,
  listStudents,
  ManagedStudent,
  ProvisionedStudent,
  provisionStudents,
  resetStudentPassword,
  setStudentExpiry,
  setStudentState,
} from "../../../src/api-client";

export default function OrganizationsPage() {
  const [prefix, setPrefix] = useState("student");
  const [count, setCount] = useState(30);
  const [classId, setClassId] = useState("class-001");
  const [password, setPassword] = useState("welcome123");
  const [batchExpiry, setBatchExpiry] = useState("");
  const [students, setStudents] = useState<ProvisionedStudent[]>([]);
  const [managed, setManaged] = useState<ManagedStudent[]>([]);
  const [search, setSearch] = useState("");
  const [filterClassId, setFilterClassId] = useState("");
  const [filterState, setFilterState] = useState<"all" | "enabled" | "disabled" | "expired">("all");
  const [status, setStatus] = useState("");

  async function refresh() {
    const session = currentSession();
    if (session) setManaged(await listStudents(session.accessToken, session.organizationId, {
      search: search.trim() || undefined,
      classId: filterClassId.trim() || undefined,
      enabled: filterState === "enabled" ? true : filterState === "disabled" ? false : undefined,
      expired: filterState === "expired" ? true : undefined,
    }));
  }

  useEffect(() => { void refresh().catch(() => setStatus("无法读取学生账号。")); }, [search, filterClassId, filterState]);

  function downloadCredentials() {
    if (students.length === 0) return setStatus("请先生成一批账号，再下载初始凭据。");
    const csv = ["账号,班级,初始密码", ...students.map((student) => [student.username, student.classId, student.initialPassword].map((value) => `"${value.replaceAll('"', '""')}"`).join(","))].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
    link.download = `学生初始凭据-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const session = currentSession();
    if (!session) return setStatus("请先登录平台管理员账号。");
    try {
      setStudents(await provisionStudents(session.accessToken, session.organizationId, { prefix, count, classId, initialPassword: password, ...(batchExpiry ? { expiresAt: new Date(batchExpiry).toISOString() } : {}) }));
      await refresh();
      setStatus("学生账号已生成。请下载或安全地发放下方的初始凭据。");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "生成账号失败。");
    }
  }

  async function toggle(student: ManagedStudent) {
    const session = currentSession();
    if (!session) return;
    try {
      await setStudentState(session.accessToken, session.organizationId, student.username, !student.enabled);
      await refresh();
      setStatus(`账号 ${student.username} 已${student.enabled ? "停用" : "启用"}。`);
    } catch {
      setStatus("更新账号状态失败。");
    }
  }

  async function resetPassword(student: ManagedStudent) {
    const session = currentSession();
    const nextPassword = window.prompt(`为 ${student.username} 设置不少于 8 位的新密码：`);
    if (!session || !nextPassword) return;
    try {
      await resetStudentPassword(session.accessToken, session.organizationId, student.username, nextPassword);
      setStatus(`已重置 ${student.username} 的密码，并使其原登录会话失效。`);
    } catch {
      setStatus("密码重置失败；请确认密码长度与管理权限。");
    }
  }

  async function setExpiry(student: ManagedStudent) {
    const session = currentSession();
    const current = student.expiresAt ? new Date(student.expiresAt).toLocaleString("zh-CN", { hour12: false }) : "";
    const value = window.prompt(`设置 ${student.username} 的到期时间（例如 2026-10-01T18:00），留空代表永久有效：`, current);
    if (!session || value === null) return;
    const expiresAt = value.trim() ? new Date(value).toISOString() : null;
    if (value.trim() && Number.isNaN(new Date(value).getTime())) return setStatus("到期时间格式不正确。");
    try {
      await setStudentExpiry(session.accessToken, session.organizationId, student.username, expiresAt);
      await refresh();
      setStatus(`已更新 ${student.username} 的有效期。`);
    } catch {
      setStatus("账号有效期更新失败。");
    }
  }

  return (
    <AdminShell active="/admin/organizations">
      <main className="admin-page">
        <div className="admin-page-heading"><div><p className="admin-eyebrow">ORGANIZATIONS & ACCOUNTS</p><h1>机构与账号</h1><p>批量创建学生账号，并管理密码、有效期和临时停用状态。</p></div></div>
        <section className="admin-panel">
          <form className="settings-form" onSubmit={submit}>
            <label>账号前缀<input value={prefix} onChange={(event) => setPrefix(event.target.value)} required /></label>
            <label>生成数量<input type="number" min="1" max="200" value={count} onChange={(event) => setCount(Number(event.target.value))} required /></label>
            <label>班级编号<input value={classId} onChange={(event) => setClassId(event.target.value)} required /></label>
            <label>统一初始密码<input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
            <label>统一截止时间（可选）<input type="datetime-local" value={batchExpiry} onChange={(event) => setBatchExpiry(event.target.value)} /></label>
            <button className="admin-primary-button" type="submit">批量生成账号</button>
          </form>
          {students.length > 0 && <div className="admin-feedback">本次已生成 {students.length} 个账号。初始密码只在本次生成结果中显示。<button type="button" onClick={downloadCredentials}>下载初始凭据 CSV</button></div>}
          {status && <div className="admin-feedback">{status}</div>}
          <div className="settings-form">
            <label>搜索账号<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="账号或用户 ID" /></label>
            <label>班级筛选<input value={filterClassId} onChange={(event) => setFilterClassId(event.target.value)} placeholder="例如 class-001" /></label>
            <label>状态筛选<select value={filterState} onChange={(event) => setFilterState(event.target.value as typeof filterState)}><option value="all">全部</option><option value="enabled">已启用</option><option value="disabled">已停用</option><option value="expired">已过期</option></select></label>
          </div>
          <div className="admin-log-table">
            <div className="admin-log-head"><span>学生账号</span><span>班级 / 状态</span><span>账号 ID</span><span>操作</span></div>
            {managed.map((student) => <div key={student.username}><span>{student.username}</span><span>{student.classId ?? "未分班"} · {student.enabled ? "已启用" : "已停用"}{student.expired ? " · 已过期" : student.expiresAt ? ` · 至 ${new Date(student.expiresAt).toLocaleString("zh-CN", { hour12: false })}` : " · 永久"}</span><span>{student.userId}</span><span><button type="button" onClick={() => void toggle(student)}>{student.enabled ? "停用" : "启用"}</button><button type="button" onClick={() => void resetPassword(student)}>重置密码</button><button type="button" onClick={() => void setExpiry(student)}>设置有效期</button></span></div>)}
          </div>
        </section>
      </main>
    </AdminShell>
  );
}
