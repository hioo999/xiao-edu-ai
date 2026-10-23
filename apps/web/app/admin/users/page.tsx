"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { StaffLifecyclePanel } from "./staff-lifecycle-panel";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import {
  createStaff,
  currentSession,
  listStaff,
  listStudents,
  ManagedStaff,
  ManagedStudent,
  resetStudentPassword,
  setAccountsExpiry,
  setAccountsState,
} from "../../../src/api-client";

type AccountRow = { username: string; userId: string; role: string; classId: string | null; enabled: boolean; expiresAt: string | null };

export default function UsersAdminPage() {
  const [students, setStudents] = useState<ManagedStudent[]>([]);
  const [staff, setStaff] = useState<ManagedStaff[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [staffUsername, setStaffUsername] = useState("");
  const [staffPassword, setStaffPassword] = useState("");
  const [staffRole, setStaffRole] = useState<"teacher" | "organization_admin">("teacher");
  const [staffExpiry, setStaffExpiry] = useState("");
  const [managedUsername, setManagedUsername] = useState("");
  const managedStaff = staff.find(item => item.username === managedUsername);

  const session = useMemo(() => currentSession(), []);
  const rows = useMemo<AccountRow[]>(() => [
    ...students.map((student) => ({ username: student.username, userId: student.userId, role: "学生", classId: student.classId, enabled: student.enabled, expiresAt: student.expiresAt })),
    ...staff.map((item) => ({ username: item.username, userId: item.userId, role: item.role === "organization_admin" ? "机构管理员" : "教师", classId: null, enabled: item.enabled, expiresAt: item.expiresAt })),
  ], [students, staff]);
  const filtered = rows.filter((row) => row.username.includes(search.trim()) || row.userId.includes(search.trim()) || (row.classId ?? "").includes(search.trim()));

  async function refresh() {
    if (!session) return;
    try {
      const [nextStudents, nextStaff] = await Promise.all([
        listStudents(session.accessToken, session.organizationId),
        listStaff(session.accessToken, session.organizationId),
      ]);
      setStudents(nextStudents);
      setStaff(nextStaff);
    } catch {
      setStatus("无法读取账号列表，请确认管理员已登录。");
    }
  }

  useEffect(() => { void refresh(); }, [session]);

  async function createTeacher(event: FormEvent) {
    event.preventDefault();
    if (!session || !staffUsername.trim() || !staffPassword.trim()) return setStatus("请填写教师/管理员账号与密码。");
    try {
      await createStaff(session.accessToken, session.organizationId, { username: staffUsername.trim(), password: staffPassword, role: staffRole, expiresAt: staffExpiry ? new Date(staffExpiry).toISOString() : null });
      setStaffUsername(""); setStaffPassword(""); setStaffExpiry("");
      setStatus("教师/管理员账号已创建。");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "创建教师账号失败。");
    }
  }

  async function bulkSetEnabled(enabled: boolean) {
    if (!session || !selected.length) return setStatus("请先勾选账号。");
    try {
      const changed = await setAccountsState(session.accessToken, session.organizationId, selected, enabled);
      setStatus(`已${enabled ? "启用" : "停用"} ${changed} 个账号。`);
      setSelected([]);
      await refresh();
    } catch {
      setStatus("批量更新失败；任教教师需先完成交接，且不能停用自己的管理账号。");
    }
  }

  async function bulkSetExpiry() {
    const value = window.prompt("为所选账号设置统一到期时间（如 2026-12-31T18:00），留空清除到期时间：");
    if (!session || !selected.length || value === null) return;
    if (value.trim() && Number.isNaN(new Date(value).getTime())) return setStatus("到期时间格式不正确。");
    const expiresAt = value.trim() ? new Date(value).toISOString() : null;
    try {
      const changed = await setAccountsExpiry(session.accessToken, session.organizationId, selected, expiresAt);
      setStatus(`已更新 ${changed} 个账号的有效期。`);
      setSelected([]);
      await refresh();
    } catch {
      setStatus("批量更新有效期失败。");
    }
  }

  async function resetPassword(username: string) {
    const nextPassword = window.prompt(`为 ${username} 设置不少于 8 位的新密码：`);
    if (!session || !nextPassword) return;
    try {
      await resetStudentPassword(session.accessToken, session.organizationId, username, nextPassword);
      setStatus(`已重置 ${username} 的密码。`);
    } catch {
      setStatus("密码重置失败，请确认该账号为学生账号。");
    }
  }

  return (
    <AdminShell active="/admin/users">
      <AdminPageLayout eyebrow="ACCOUNT LIFECYCLE" title="账号管理" description="统一查看学生与教师账号，批量启停、设置有效期和重置密码。" actions={<>
            <button className="admin-primary-button" type="button" onClick={() => void bulkSetEnabled(true)}>批量启用</button>
            <button className="admin-button--quiet" type="button" onClick={() => void bulkSetEnabled(false)}>批量停用</button>
            <button className="admin-button--quiet" type="button" onClick={() => void bulkSetExpiry()}>批量设置有效期</button>
          </>}>
        <AdminSection title="创建工作人员账号" description="教师和机构管理员用于教学运营，不与学生账号混用。">
          <form className="settings-form" onSubmit={createTeacher}>
            <label>教师/管理员账号<input value={staffUsername} onChange={(event) => setStaffUsername(event.target.value)} placeholder="teacher-01" required /></label>
            <label>初始密码<input type="password" minLength={8} value={staffPassword} onChange={(event) => setStaffPassword(event.target.value)} required /></label>
            <label>角色<select value={staffRole} onChange={(event) => setStaffRole(event.target.value as "teacher" | "organization_admin")}><option value="teacher">教师</option><option value="organization_admin">机构管理员</option></select></label>
            <label>截止时间（可选）<input type="datetime-local" value={staffExpiry} onChange={(event) => setStaffExpiry(event.target.value)} /></label>
            <button className="admin-primary-button" type="submit">创建账号</button>
          </form>
          {status && <div className="admin-feedback">{status}</div>}
          <div className="settings-form admin-filter-form">
            <label>搜索账号<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="账号、用户 ID 或班级" /></label>
          </div>
        </AdminSection>
        <AdminSection title="账号目录" description={`${filtered.length} 个账号匹配当前搜索条件。`}>
          <div className="admin-log-table">
            <div className="admin-log-head"><span>全选 <input type="checkbox" checked={filtered.length > 0 && filtered.every((row) => selected.includes(row.username))} onChange={(event) => setSelected(event.target.checked ? filtered.map((row) => row.username) : [])} /></span><span>账号</span><span>角色 / 班级</span><span>状态</span><span>操作</span></div>
            {filtered.map((row) => <div key={row.userId}><span><input type="checkbox" checked={selected.includes(row.username)} onChange={(event) => setSelected((prev) => event.target.checked ? [...prev, row.username] : prev.filter((item) => item !== row.username))} /></span><span>{row.username}<small> · {row.userId}</small></span><span>{row.role}{row.classId ? ` · ${row.classId}` : ""}</span><span>{row.enabled ? "已启用" : "已停用"}{row.expiresAt ? ` · 至 ${new Date(row.expiresAt).toLocaleString("zh-CN", { hour12: false })}` : " · 永久"}</span><span>{row.role === "学生" ? <button type="button" onClick={() => void resetPassword(row.username)}>重置密码</button> : <button type="button" aria-label={`管理 ${row.username}`} disabled={row.userId === session?.userId} onClick={() => setManagedUsername(row.username)}>管理账号</button>}</span></div>)}
            {filtered.length === 0 && <div><span>暂无匹配账号</span><span>—</span><span>—</span><span>—</span><span>—</span></div>}
          </div>
        </AdminSection>
        {managedStaff && session && <StaffLifecyclePanel key={managedStaff.userId} staff={managedStaff} colleagues={staff} session={session} onChanged={refresh} onClose={() => setManagedUsername("")} />}
      </AdminPageLayout>
    </AdminShell>
  );
}
