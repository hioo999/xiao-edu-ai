"use client";

import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { clearSession, currentSession, PlatformSession } from "../../../src/api-client";

const groups = [
  { label: "平台概览", items: [{ href: "/admin", label: "工作台", icon: "⌂" }] },
  { label: "教学运营", items: [
    { href: "/admin/organizations", label: "机构与账号", icon: "◎" },
    { href: "/admin/users", label: "账号管理", icon: "◉" },
    { href: "/admin/courses", label: "课程与教学", icon: "▣" },
    { href: "/admin/classrooms", label: "课堂管理", icon: "◌" },
    { href: "/admin/showcase", label: "作品与案例", icon: "✦" },
    { href: "/admin/inspiration", label: "灵感库", icon: "☼" },
  ] },
  { label: "AI 中台", items: [
    { href: "/admin/providers", label: "AI 能力中心", icon: "◈" },
    { href: "/admin/polish", label: "提示词润色", icon: "✧" },
    { href: "/admin/agents", label: "智能体与工具", icon: "✺" },
    { href: "/admin/quotas", label: "额度与成本", icon: "◫" },
  ] },
  { label: "平台治理", items: [
    { href: "/admin/assets", label: "文件与资源", icon: "▤" },
    { href: "/admin/jobs", label: "生成任务", icon: "↻" },
    { href: "/admin/moderation", label: "安全审核", icon: "☂" },
    { href: "/admin/audit", label: "安全与审计", icon: "✓" },
    { href: "/admin/operations", label: "系统运维", icon: "⇄" },
    { href: "/admin/settings", label: "系统设置", icon: "⌘" },
  ] },
];

export function AdminShell({ children, active = "/admin" }: { children: ReactNode; active?: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const [session, setSession] = useState<PlatformSession | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const current = currentSession();
    if (!current || !["platform_admin", "organization_admin"].includes(current.role)) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    setSession(current);
    setIsCheckingSession(false);
  }, [pathname, router]);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (isCheckingSession || !session) {
    return <main className="admin-session-check"><span>✦</span><p>正在验证管理员登录状态…</p></main>;
  }

  const roleLabel = session.role === "platform_admin" ? "平台管理员" : "机构管理员";
  const avatarLabel = session.role === "platform_admin" ? "管" : "机";
  return <div className={`admin-shell ${collapsed ? "admin-shell--collapsed" : ""}`}>
    <aside className="admin-sidebar">
      <div className="admin-brand"><span>✦</span>{!collapsed && <div><strong>星芽 AI</strong><small>平台管理中心</small></div>}</div>
      <nav className="admin-nav">{groups.map((group) => <div className="admin-nav-group" key={group.label}>
        {!collapsed && <p>{group.label}</p>}
        {group.items.map((item) => <a className={active === item.href ? "is-active" : ""} href={item.href} key={item.href} title={item.label}><i>{item.icon}</i>{!collapsed && <span>{item.label}</span>}</a>)}
      </div>)}</nav>
      <button className="admin-collapse" type="button" onClick={() => setCollapsed((value) => !value)}>{collapsed ? "→" : "← 收起菜单"}</button>
    </aside>
    <section className="admin-main">
      <header className="admin-topbar"><div><span className="admin-breadcrumb">平台管理 /</span><strong>星芽 AI 创作学习平台</strong></div><div className="admin-topbar__actions"><span className="admin-live-dot">系统运行正常</span><span className="admin-user-label">{roleLabel} · {session.userId}</span><span className="admin-avatar" title={roleLabel}>{avatarLabel}</span><button className="admin-logout" type="button" onClick={logout}>退出</button></div></header>
      <div className="admin-content">{children}</div>
    </section>
  </div>;
}
