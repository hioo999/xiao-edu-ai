"use client";

import { FormEvent, useEffect, useState } from "react";
import { ManagedStaff, PlatformSession } from "../../../src/api-client";
import { getStaffHandoverPlan, handoverStaff, listStaffHandovers, resetStaffPassword, revokeStaffSessions, setStaffEnabled, setStaffExpiry, StaffHandover, StaffHandoverPlan } from "../../../src/staff-api";
import { AdminSection } from "../components/admin-page-layout";


export function StaffLifecyclePanel({ staff, colleagues, session, onChanged, onClose }: {
  staff: ManagedStaff; colleagues: ManagedStaff[]; session: PlatformSession;
  onChanged: () => Promise<void>; onClose: () => void;
}) {
  const [plan, setPlan] = useState<StaffHandoverPlan | null>(null);
  const [history, setHistory] = useState<StaffHandover[]>([]);
  const [password, setPassword] = useState("");
  const [expiry, setExpiry] = useState(staff.expiresAt ? new Date(new Date(staff.expiresAt).getTime() - new Date(staff.expiresAt).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "");
  const [replacement, setReplacement] = useState("");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const candidates = colleagues.filter(item => item.role === "teacher" && item.userId !== staff.userId && item.enabled && (!item.expiresAt || new Date(item.expiresAt).getTime() > Date.now()));
  const hasResources = Boolean(plan && (plan.classIds.length || plan.courseIds.length));

  async function load() {
    const [nextPlan, nextHistory] = await Promise.all([
      getStaffHandoverPlan(session.accessToken, session.organizationId, staff.username),
      listStaffHandovers(session.accessToken, session.organizationId, staff.username),
    ]);
    setPlan(nextPlan); setHistory(nextHistory);
  }

  useEffect(() => { void load().catch(error => setMessage(error instanceof Error ? error.message : "无法读取教师交接信息。")); }, [staff.userId, session.accessToken]);

  async function execute(action: () => Promise<unknown>, success: string) {
    setBusy(true); setMessage("");
    try {
      await action();
      setMessage(success);
      try { await onChanged(); await load(); }
      catch { setMessage(`${success} 列表暂未刷新，请稍后重新打开管理面板。`); }
    } catch (error) { setMessage(error instanceof Error ? error.message : "操作失败，请刷新后重试。"); }
    finally { setBusy(false); }
  }

  function reset(event: FormEvent) {
    event.preventDefault();
    void execute(async () => { await resetStaffPassword(session.accessToken, session.organizationId, staff.username, password); setPassword(""); }, "密码已重置，旧登录会话和课堂协助授权已撤销。");
  }

  function saveExpiry(event: FormEvent) {
    event.preventDefault();
    if (expiry && Number.isNaN(new Date(expiry).getTime())) return setMessage("请选择有效的到期日期和时间。");
    void execute(() => setStaffExpiry(session.accessToken, session.organizationId, staff.username, expiry ? new Date(expiry).toISOString() : null), "账号有效期已更新。");
  }

  function handover(event: FormEvent) {
    event.preventDefault();
    if (!confirmed || !replacement || !reason.trim()) return setMessage("请选择接任教师、填写原因并确认交接范围。");
    void execute(async () => { await handoverStaff(session.accessToken, session.organizationId, staff.username, replacement, reason.trim()); setReason(""); setConfirmed(false); }, "交接已完成：班级和课程已移交，原教师账号已停用并强制下线。");
  }

  return <AdminSection title={`${staff.username} · 账号安全与教学交接`} description="按账号管理凭据和有效期；教师离职必须先交接教学资源，不能直接遗留无人负责的班级。" toolbar={<button type="button" disabled={busy} onClick={onClose}>收起管理</button>}>
    <p>角色：{staff.role === "teacher" ? "教师" : "机构管理员"} · {staff.enabled ? "已启用" : "已停用"}</p>
    {message && <p className="admin-feedback" role="status">{message}</p>}
    <div className="admin-toolbar">
      <button type="button" disabled={busy || (staff.enabled && hasResources)} onClick={() => void execute(() => setStaffEnabled(session.accessToken, session.organizationId, staff.username, !staff.enabled), staff.enabled ? "账号已停用，旧会话已撤销。" : "账号已启用。")}>{staff.enabled ? "停用账号" : "启用账号"}</button>
      <button type="button" disabled={busy} onClick={() => void execute(() => revokeStaffSessions(session.accessToken, session.organizationId, staff.username), "已强制下线，并撤销课堂协助授权。")}>强制下线</button>
    </div>
    <form className="settings-form" onSubmit={reset}>
      <label>新密码（至少 8 位）<input type="password" minLength={8} maxLength={256} autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>
      <button type="submit" disabled={busy} className="admin-primary-button">重置工作人员密码</button>
    </form>
    <form className="settings-form" onSubmit={saveExpiry}>
      <label>工作人员有效期<input type="datetime-local" value={expiry} onChange={event => setExpiry(event.target.value)} /></label>
      <p>按当前电脑的本地时间选择；留空并保存表示不设置到期时间。</p>
      <button type="submit" disabled={busy}>保存工作人员有效期</button>
    </form>
    {staff.role === "teacher" && <div>
      <h3>离职交接</h3>
      {plan ? <p>任教班级：{plan.classIds.join("、") || "无"}；负责课程：{plan.courseIds.join("、") || "无"}。</p> : <p>正在读取教学资源，请稍候…</p>}
      <p>交接将保留其他任课教师、学生作品和学习记录；教师私人资料不自动转移。</p>
      <form className="settings-form" onSubmit={handover}>
        <label>接任教师<select value={replacement} onChange={event => setReplacement(event.target.value)} required><option value="">请选择有效教师</option>{candidates.map(item => <option key={item.userId} value={item.userId}>{item.username}</option>)}</select></label>
        <label>交接原因<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={500} required placeholder="例如：教师离职，由接任老师继续授课" /></label>
        <label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} required />我已确认移交上述全部班级和课程，并停用原教师账号</label>
        <button type="submit" className="admin-primary-button" disabled={busy || !hasResources || !candidates.length || !confirmed}>确认交接并停用</button>
      </form>
      {!candidates.length && <p>尚无可接任的有效教师，请先创建并启用接任教师账号。</p>}
      <h3>交接记录</h3>
      {history.length ? <ul>{history.map(item => <li key={item.handoverId}>{new Date(item.createdAt).toLocaleString("zh-CN")} · 接任：{colleagues.find(colleague => colleague.userId === item.replacementUserId)?.username ?? item.replacementUserId} · {item.reason}</li>)}</ul> : <p>暂无交接记录。</p>}
    </div>}
  </AdminSection>;
}
