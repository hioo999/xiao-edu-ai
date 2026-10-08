"use client";

import { FormEvent, useState } from "react";

import { AuthIllustration } from "../components/auth-illustration";
import { bootstrapAdmin, saveSession } from "../../src/api-client";

export default function SetupPage() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [organizationId, setOrganizationId] = useState("org-001");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      saveSession(await bootstrapAdmin(username, password, organizationId));
      window.location.assign("/admin/providers");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "初始化失败。");
    }
  }

  return <main className="auth-page">
    <AuthIllustration />
    <section className="auth-panel auth-panel--admin">
      <a className="auth-panel__back" href="/login">← 返回登录</a>
      <div className="auth-card auth-card--admin">
        <span className="auth-card__mascot" aria-hidden="true">⚙</span>
        <p className="auth-card__eyebrow">FIRST-TIME SETUP</p>
        <h1>创建平台管理员</h1>
        <p className="auth-card__intro">仅首次安装时使用。请设置只有你自己掌握的强密码。</p>
        <form onSubmit={submit}>
          <label>管理员账号<input value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} required /></label>
          <label>管理员密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /></label>
          <label>机构编号<input value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} required /></label>
          <button type="submit">创建并进入后台  →</button>
        </form>
        {message && <p className="auth-card__message" role="alert">{message}</p>}
        <a className="auth-card__switch" href="/login">已有管理员账号？去登录</a>
      </div>
      <p className="auth-panel__note">仅管理员可见 · 账号安全由你掌控</p>
    </section>
  </main>;
}
