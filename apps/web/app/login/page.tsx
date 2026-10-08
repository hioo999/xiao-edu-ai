"use client";

import { useEffect, useState } from "react";
import { AuthIllustration } from "../components/auth-illustration";
import { destinationForRole, login, saveSession } from "../../src/api-client";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAdminLogin, setIsAdminLogin] = useState(false);

  useEffect(() => {
    setIsAdminLogin(new URLSearchParams(window.location.search).get("next")?.startsWith("/admin") ?? false);
  }, []);

  async function submit() {
    if (!username.trim() || !password) { setMessage("请输入平台账号和密码。"); return; }
    setIsSubmitting(true);
    setMessage("");
    try {
      const session = await login(username.trim(), password);
      saveSession(session);
      const next = new URLSearchParams(window.location.search).get("next");
      const canOpenRequestedAdminPage = next?.startsWith("/admin") && ["platform_admin", "organization_admin"].includes(session.role);
      window.location.assign(canOpenRequestedAdminPage ? next : destinationForRole(session.role));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "暂时无法登录，请稍后再试。");
    } finally { setIsSubmitting(false); }
  }

  return <main className="auth-page">
    <AuthIllustration />
    <section className="auth-panel">
      <a className="auth-panel__back" href="/">← 返回创作岛</a>
      <div className="auth-card">
        <span className="auth-card__mascot" aria-hidden="true">✦</span>
        <p className="auth-card__eyebrow">{isAdminLogin ? "ADMINISTRATOR ACCESS" : "WELCOME BACK"}</p>
        <h1>{isAdminLogin ? "管理员登录" : "欢迎回来！"}</h1>
        <p className="auth-card__intro">{isAdminLogin ? "请输入已创建的平台管理员账号，验证后将返回 AI 能力中心。" : "输入老师分配的账号，就可以开始 AI 创作，不需要注册其他工具。"}</p>
        <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <label>{isAdminLogin ? "管理员账号" : "我的平台账号"}<input value={username} onChange={(event) => setUsername(event.target.value)} placeholder={isAdminLogin ? "请输入管理员账号" : "例如：AI2026001"} autoComplete="username" /></label>
          <label>登录密码<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="请输入密码" autoComplete="current-password" /></label>
          <button disabled={isSubmitting} type="submit">{isSubmitting ? "正在验证身份…" : isAdminLogin ? "进入管理后台  →" : "进入我的创作岛  →"}</button>
        </form>
        {message && <div className="auth-card__message" role="alert">{message}</div>}
        <p className="auth-card__help">{isAdminLogin ? "忘记管理员密码？请联系平台负责人处理。" : "忘记账号或密码？请联系老师或管理员。"}</p>
      </div>
      <p className="auth-panel__note">专属学习账号 · 安全课堂环境</p>
    </section>
  </main>;
}
