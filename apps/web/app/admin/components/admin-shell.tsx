"use client";

import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Archive,
  Bot,
  BrainCircuit,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Database,
  FileStack,
  Gauge,
  GraduationCap,
  KeyRound,
  LayoutDashboard,
  Library,
  ListChecks,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  MonitorCog,
  Palette,
  Settings,
  ShieldCheck,
  Sparkles,
  UsersRound,
  WalletCards,
  WandSparkles,
  type LucideIcon,
} from "lucide-react";

import { clearSession, currentSession, PlatformSession } from "../../../src/api-client";

type AdminNavItem = { href: string; label: string; icon: LucideIcon; description?: string };

const groups: Array<{ label: string; items: AdminNavItem[] }> = [
  { label: "平台概览", items: [{ href: "/admin", label: "工作台", icon: LayoutDashboard, description: "关键运营指标" }] },
  { label: "教学运营", items: [
    { href: "/admin/organizations", label: "机构与账号", icon: Building2, description: "机构和批量账号" },
    { href: "/admin/users", label: "账号管理", icon: UsersRound, description: "师生生命周期" },
    { href: "/admin/courses", label: "课程与教学", icon: GraduationCap, description: "课程发布和课件" },
    { href: "/admin/classrooms", label: "课堂管理", icon: MonitorCog, description: "课堂与在线状态" },
    { href: "/admin/showcase", label: "作品与案例", icon: Palette, description: "作品墙和示例" },
    { href: "/admin/inspiration", label: "灵感库", icon: Sparkles, description: "灵感卡片" },
  ] },
  { label: "AI 能力中心", items: [
    { href: "/admin/providers", label: "AI 能力中心", icon: BrainCircuit, description: "模型和降级链路" },
    { href: "/admin/polish", label: "提示词润色", icon: WandSparkles, description: "学生输入优化" },
    { href: "/admin/agents", label: "智能体", icon: Bot, description: "学生可用的 AI 伙伴" },
    { href: "/admin/skills", label: "Skills", icon: Archive, description: "可复用能力" },
    { href: "/admin/mcp", label: "MCP 工具", icon: Database, description: "外部工具连接" },
    { href: "/admin/knowledge", label: "知识库", icon: Library, description: "课程知识与检索" },
    { href: "/admin/quotas", label: "额度与成本", icon: WalletCards, description: "Token 与任务额度" },
  ] },
  { label: "平台治理", items: [
    { href: "/admin/assets", label: "文件与资源", icon: FileStack, description: "上传和存储" },
    { href: "/admin/jobs", label: "生成任务", icon: ListChecks, description: "队列和重试" },
    { href: "/admin/moderation", label: "安全审核", icon: ShieldCheck, description: "内容风控" },
    { href: "/admin/audit", label: "安全与审计", icon: ClipboardCheck, description: "操作追踪" },
    { href: "/admin/operations", label: "系统运维", icon: Gauge, description: "健康和备份" },
    { href: "/admin/settings", label: "系统设置", icon: Settings, description: "全局开关" },
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
    return <main className="admin-session-check"><span><LoaderCircle size={24} aria-hidden="true" /></span><p>正在验证管理员登录状态…</p></main>;
  }

  const roleLabel = session.role === "platform_admin" ? "平台管理员" : "机构管理员";
  const avatarLabel = session.role === "platform_admin" ? "管" : "机";
  const activeLabel = groups.flatMap((group) => group.items).find((item) => active === item.href)?.label ?? "工作台";
  return <div className={`admin-shell ${collapsed ? "admin-shell--collapsed" : ""}`}>
    <aside className="admin-sidebar" aria-label="后台主导航">
      <div className="admin-brand"><span><KeyRound size={21} aria-hidden="true" /></span>{!collapsed && <div><strong>星芽 AI</strong><small>运营控制台</small></div>}</div>
      <nav className="admin-nav">{groups.map((group) => <div className="admin-nav-group" key={group.label}>
        {!collapsed && <p>{group.label}</p>}
        {group.items.map((item) => {
          const Icon = item.icon;
          return <a className={active === item.href ? "is-active" : ""} href={item.href} key={item.href} title={item.label} aria-current={active === item.href ? "page" : undefined}><i><Icon size={18} strokeWidth={2} aria-hidden="true" /></i>{!collapsed && <span><b>{item.label}</b>{item.description && <small>{item.description}</small>}</span>}</a>;
        })}
      </div>)}</nav>
      <button className="admin-collapse" type="button" aria-label={collapsed ? "展开后台菜单" : "收起后台菜单"} onClick={() => setCollapsed((value) => !value)}>{collapsed ? <ChevronRight size={18} aria-hidden="true" /> : <><ChevronLeft size={17} aria-hidden="true" /> 收起菜单</>}</button>
    </aside>
    <section className="admin-main">
      <header className="admin-topbar"><div className="admin-topbar__title"><span className="admin-breadcrumb">平台管理 / {activeLabel}</span><strong>星芽 AI 创作学习平台</strong></div><div className="admin-topbar__actions"><span className="admin-live-dot" role="status"><Activity size={14} aria-hidden="true" /> 系统运行正常</span><span className="admin-user-label"><LockKeyhole size={14} aria-hidden="true" /> {roleLabel} · {session.userId}</span><span className="admin-avatar" title={roleLabel} aria-label={roleLabel}>{avatarLabel}</span><button className="admin-logout" type="button" onClick={logout}><LogOut size={14} aria-hidden="true" /> 退出</button></div></header>
      <div className="admin-content">{children}</div>
    </section>
  </div>;
}
