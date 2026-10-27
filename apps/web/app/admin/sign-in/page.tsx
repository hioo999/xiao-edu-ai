"use client";

import { useState } from "react";
import { AuthIllustration } from "../../components/auth-illustration";
import { adminLogin, saveSession } from "../../../src/api-client";

export default function AdminSignInPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function submit() {
    if (!username.trim() || !password) return setMessage("请输入管理员账号和密码。");
    setPending(true);
    setMessage("");
    try {
      const session = await adminLogin(username.trim(), password);
      saveSession(session);
      const next = new URLSearchParams(window.location.search).get("next");
      window.location.assign(next?.startsWith("/admin") && !next.startsWith("//") && !next.startsWith("/admin/sign-in") ? next : "/admin");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "暂时无法登录后台。");
    } finally {
      setPending(false);
    }
  }

  return <main className="auth-page"><AuthIllustration /><section className="auth-panel auth-panel--admin">
    <a className="auth-panel__back" href="/">← 返回创作岛</a>
    <div className="auth-card auth-card--admin">
      <span className="auth-card__mascot" aria-hidden="true">✦</span>
      <p className="auth-card__eyebrow">ADMINISTRATOR ACCESS</p>
      <h1>管理员登录</h1>
      <p className="auth-card__intro">仅授权管理员可进入运营控制台。</p>
      <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        <label>管理员账号<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required /></label>
        <label>登录密码<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required /></label>
        <button disabled={pending} type="submit">{pending ? "正在验证身份…" : "进入管理后台  →"}</button>
      </form>
      {message && <div className="auth-card__message" role="alert">{message}</div>}
    </div>
  </section></main>;
}
