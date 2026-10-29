"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import {
  currentSession,
  grantStudentCredits,
  studentCreditDetail,
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
  const [initialCredits, setInitialCredits] = useState(100);
  const [classId, setClassId] = useState("class-001");
  const [password, setPassword] = useState("welcome123");
  const [batchExpiry, setBatchExpiry] = useState("");
  const [students, setStudents] = useState<ProvisionedStudent[]>([]);
  const [managed, setManaged] = useState<ManagedStudent[]>([]);
  const [search, setSearch] = useState("");
  const [filterClassId, setFilterClassId] = useState("");
  const [filterState, setFilterState] = useState<"all" | "enabled" | "disabled" | "expired">("all");
  const [status, setStatus] = useState("");
  const [creditDetail, setCreditDetail] = useState<{ username: string; granted: number; spent: number; reserved: number; balance: number } | null>(null);

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
  const accountStats = { total: managed.length, enabled: managed.filter((student) => student.enabled && !student.expired).length, disabled: managed.filter((student) => !student.enabled).length, expired: managed.filter((student) => student.expired).length };

  function downloadCredentials() {
    if (students.length === 0) return setStatus("请先生成一批账号，再下载初始凭据。");
    const csv = ["账号,班级,初始密码,初始积分", ...students.map((student) => [student.username, student.classId, student.initialPassword, String(student.initialCredits)].map((value) => `"${value.replaceAll('"', '""')}"`).join(","))].join("\n");
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
      setStudents(await provisionStudents(session.accessToken, session.organizationId, { prefix, count, classId, initialPassword: password, initialCredits, ...(batchExpiry ? { expiresAt: new Date(batchExpiry).toISOString() } : {}) }));
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

  async function showCreditDetail(student: ManagedStudent) {
    const session = currentSession();
    if (!session) return;
    try { const detail = await studentCreditDetail(session.accessToken, student.userId); setCreditDetail({ username: student.username, ...detail }); }
    catch { setStatus("无法读取该学生的积分明细。"); }
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

  async function addCredits(student: ManagedStudent) {
    const session = currentSession();
    const value = window.prompt(`为 ${student.username} 增加多少积分？`, "100");
    if (!session || value === null) return;
    const amount = Number(value);
    if (!Number.isInteger(amount) || amount <= 0 || amount > 1000000) return setStatus("积分必须是 1 到 1000000 的整数。");
    try {
      const wallet = await grantStudentCredits(session.accessToken, student.userId, amount);
      setStatus(`${student.username} 已增加 ${amount} 积分，当前可用 ${wallet.balance} 积分。`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "添加积分失败。");
    }
  }

  return (
    <AdminShell active="/admin/organizations">
      <AdminPageLayout eyebrow="ORGANIZATIONS & ACCOUNTS" title="机构与账号" description="批量创建学生账号，并管理密码、有效期和临时停用状态。">
        <AdminSection title="批量生成学生账号" description="一次设置班级、数量、初始密码、每人初始积分和有效期，生成后可下载凭据。">
          <form className="settings-form" onSubmit={submit}>
            <label>账号前缀<input value={prefix} onChange={(event) => setPrefix(event.target.value)} required /></label>
            <label>生成数量<input type="number" min="1" max="200" value={count} onChange={(event) => setCount(Number(event.target.value))} required /></label>
            <label>班级编号<input value={classId} onChange={(event) => setClassId(event.target.value)} required /></label>
            <label>统一初始密码<input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
            <label>每位学生初始积分<input type="number" min="0" max="1000000" value={initialCredits} onChange={(event) => setInitialCredits(Number(event.target.value))} required /><small>默认 100 分；AI 创作按实际用量扣除，余额不足时停止生成。</small></label>
            <label>统一截止时间（可选）<input type="datetime-local" value={batchExpiry} onChange={(event) => setBatchExpiry(event.target.value)} /></label>
            <button className="admin-primary-button" type="submit">批量生成账号</button>
          </form>
          {students.length > 0 && <div className="admin-feedback">本次已生成 {students.length} 个账号。初始密码只在本次生成结果中显示。<button type="button" onClick={downloadCredentials}>下载初始凭据 CSV</button></div>}
          {status && <div className="admin-feedback">{status}</div>}
          <div className="settings-form admin-filter-form">
            <label>搜索账号<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="账号或用户 ID" /></label>
            <label>班级筛选<input value={filterClassId} onChange={(event) => setFilterClassId(event.target.value)} placeholder="例如 class-001" /></label>
            <label>状态筛选<select value={filterState} onChange={(event) => setFilterState(event.target.value as typeof filterState)}><option value="all">全部</option><option value="enabled">已启用</option><option value="disabled">已停用</option><option value="expired">已过期</option></select></label>
          </div>
        </AdminSection>
        <div className="account-health-strip"><article><small>当前结果</small><strong>{accountStats.total}</strong><span>个账号</span></article><article className="is-ready"><small>正常启用</small><strong>{accountStats.enabled}</strong><span>可正常进入平台</span></article><article className={accountStats.disabled ? "is-warning" : "is-ready"}><small>已停用</small><strong>{accountStats.disabled}</strong><span>需要重新启用或确认</span></article><article className={accountStats.expired ? "is-warning" : "is-ready"}><small>已过期</small><strong>{accountStats.expired}</strong><span>建议更新有效期</span></article></div>
        <AdminSection title="学生账号目录" description={`${managed.length} 个账号匹配当前筛选条件。`}>          <div className="admin-log-table">
            <div className="admin-log-head"><span>学生账号</span><span>班级 / 状态</span><span>账号 ID</span><span>操作</span></div>
            {managed.map((student) => <div key={student.username}><span>{student.username}</span><span>{student.classId ?? "未分班"} · {student.enabled ? "已启用" : "已停用"}{student.expired ? " · 已过期" : student.expiresAt ? ` · 至 ${new Date(student.expiresAt).toLocaleString("zh-CN", { hour12: false })}` : " · 永久"}</span><span>{student.userId}<small> · 余额 {student.creditBalance ?? "未设置"} 积分</small></span><span><button type="button" onClick={() => void showCreditDetail(student)}>积分明细</button><button type="button" onClick={() => void toggle(student)}>{student.enabled ? "停用" : "启用"}</button><button type="button" onClick={() => void resetPassword(student)}>重置密码</button><button type="button" onClick={() => void setExpiry(student)}>设置有效期</button><button type="button" onClick={() => void addCredits(student)}>增加积分</button></span></div>)}
          </div>
        </AdminSection>
        {creditDetail && <div className="admin-feedback"><strong>{creditDetail.username} 的积分明细：</strong> 总额度 {creditDetail.granted} · 已消耗 {creditDetail.spent} · 预占用 {creditDetail.reserved} · 剩余 {creditDetail.balance}<button type="button" onClick={() => setCreditDetail(null)}>关闭</button></div>}
      </AdminPageLayout>
    </AdminShell>
  );
}
