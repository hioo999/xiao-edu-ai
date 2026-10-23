"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "../components/admin-shell";
import { AdminPageLayout, AdminSection } from "../components/admin-page-layout";
import { currentSession, getOrganizationSettings, OrganizationSettings, revokeOrganizationSessions, saveOrganizationSettings } from "../../../src/api-client";

const defaults: OrganizationSettings = { displayName: "星芽 AI 创作学习平台", studentHomeEnabled: true, maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all", videoDurationSeconds: 5 };

export default function SettingsPage() {
  const [settings, setSettings] = useState<OrganizationSettings>(defaults);
  const [status, setStatus] = useState("");
  useEffect(() => { const session = currentSession(); if (session) void getOrganizationSettings(session.accessToken).then(setSettings).catch((error) => setStatus(error instanceof Error ? error.message : "无法读取系统设置。")); }, []);
  async function submit(event: FormEvent) { event.preventDefault(); const session = currentSession(); if (!session) return setStatus("请先登录管理员账号。"); try { setSettings(await saveOrganizationSettings(session.accessToken, settings)); setStatus("系统设置已持久化保存。 "); } catch (error) { setStatus(error instanceof Error ? error.message : "保存失败。"); } }
  async function revokeSessions() { const session = currentSession(); if (!session || !window.confirm("将强制下线本机构所有其他已登录账号，确定继续吗？")) return; try { const revoked = await revokeOrganizationSessions(session.accessToken); setStatus(`已强制下线 ${revoked} 个其他登录会话。`); } catch { setStatus("强制下线失败。"); } }
  return <AdminShell active="/admin/settings"><AdminPageLayout eyebrow="PLATFORM SETTINGS" title="系统与安全设置" description="设置机构显示名称、学生端开放状态、视频时长和应急会话处置。">{status && <div className="admin-feedback" role="status">{status}</div>}<AdminSection title="平台基础设置" description="这些配置会影响学生端入口和平台提示。"><form className="settings-form" onSubmit={submit}><label>平台显示名称<input value={settings.displayName} onChange={(event) => setSettings({ ...settings, displayName: event.target.value })} required /></label><label>维护提示<textarea value={settings.maintenanceMessage} onChange={(event) => setSettings({ ...settings, maintenanceMessage: event.target.value })} placeholder="仅在维护时向学生展示" /></label><label className="api-editor__switches"><input type="checkbox" checked={settings.studentHomeEnabled} onChange={(event) => setSettings({ ...settings, studentHomeEnabled: event.target.checked })} /> 允许学生进入创作大厅</label><label>学生视频生成时长<select value={settings.videoDurationSeconds} onChange={(event) => setSettings({ ...settings, videoDurationSeconds: Number(event.target.value) as 5 | 10 })}><option value={5}>5 秒</option><option value={10}>10 秒</option></select></label><p className="admin-section__note">此设置对本机构新提交的视频任务生效；模型需支持所选时长。</p><button className="admin-primary-button" type="submit">保存系统设置</button></form></AdminSection><AdminSection title="会话安全" description="账号停用、密码重置和有效期结束会自动失效；发生异常时可立即让其他账号重新登录。" toolbar={<button type="button" className="admin-button--quiet" onClick={() => void revokeSessions()}>强制其他账号下线</button>}><p className="admin-section__note">执行强制下线后，本机构其他账号需要重新登录。</p></AdminSection></AdminPageLayout></AdminShell>;
}
