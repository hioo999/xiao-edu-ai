export interface NavigationItem {
  id: string;
  label: string;
  href: string;
  icon: string;
  description: string;
}

export const studentNavigation: NavigationItem[] = [
  { id: "chat", label: "AI 对话", href: "/workspace/chat", icon: "💬", description: "和 AI 一起想清楚、写清楚。" },
  { id: "html", label: "网页创作", href: "/workspace/html", icon: "🌐", description: "用自然语言做出互动网页。" },
  { id: "image", label: "图片创作", href: "/workspace/image", icon: "🎨", description: "把想法变成画面和海报。" },
  { id: "music", label: "音乐创作", href: "/workspace/music", icon: "🎵", description: "创作歌词、旋律和声音。" },
  { id: "video", label: "视频创作", href: "/workspace/video", icon: "🎬", description: "让故事、镜头和角色动起来。" },
  { id: "agents", label: "智能体中心", href: "/agents", icon: "🤖", description: "选择适合你的 AI 伙伴。" },
  { id: "inspiration", label: "灵感中心", href: "/inspiration", icon: "💡", description: "从案例开始，不再面对空白。" },
  { id: "projects", label: "我的项目", href: "/projects", icon: "🖼️", description: "管理你的跨模态作品。" },
  { id: "courses", label: "AI 课程", href: "/courses", icon: "📚", description: "跟着课程和挑战一步步学习。" },
  { id: "assets", label: "我的素材", href: "/assets", icon: "🎒", description: "查看图片、音乐、视频和文件。" },
  { id: "reports", label: "成长报告", href: "/student/reports", icon: "🌱", description: "回顾你的创作和学习成长。" },
];

export const teacherNavigation: NavigationItem[] = [
  { id: "today", label: "今日课堂", href: "/teacher", icon: "⌂", description: "快速查看今天的教学安排。" },
  { id: "classes", label: "班级管理", href: "/teacher/classes", icon: "◎", description: "管理班级、学生和课堂状态。" },
  { id: "students", label: "学生状态", href: "/teacher/classroom", icon: "◌", description: "查看在线状态和辅导需求。" },
  { id: "courses", label: "课程管理", href: "/teacher/courses", icon: "▣", description: "创建和编辑 AI 课程。" },
  { id: "flows", label: "教学流程", href: "/teacher/flows", icon: "≋", description: "编排步骤、任务和挑战。" },
  { id: "review", label: "作品审核", href: "/teacher/review", icon: "✓", description: "审核学生生成内容和分享。" },
  { id: "parents", label: "家校沟通", href: "/teacher/parents", icon: "♡", description: "向家长发布学习反馈和通知。" },
  { id: "reports", label: "学习报告", href: "/teacher/reports", icon: "◫", description: "查看班级和学生成长数据。" },
  { id: "knowledge", label: "知识库", href: "/teacher/knowledge", icon: "▤", description: "管理课程和机构知识资料。" },
  { id: "exports", label: "课程导出", href: "/teacher/exports", icon: "⇩", description: "导出课程、作品和报告。" },
];

export const adminNavigation: NavigationItem[] = [
  { id: "organizations", label: "机构管理", href: "/admin/organizations", icon: "⌂", description: "管理学校和培训机构。" },
  { id: "users", label: "账号管理", href: "/admin/users", icon: "◎", description: "管理教师、班级和学生账号。" },
  { id: "parents", label: "家长账号", href: "/admin/parents", icon: "♧", description: "创建家长账号并绑定学生。" },
  { id: "providers", label: "模型配置", href: "/admin/providers", icon: "◈", description: "配置文字、图片、视频和语音模型。" },
  { id: "quotas", label: "额度与存储", href: "/admin/quotas", icon: "◫", description: "查看额度、任务和存储使用情况。" },
  { id: "knowledge", label: "知识库", href: "/admin/knowledge", icon: "▤", description: "管理平台和机构知识库。" },
  { id: "skills", label: "Skill 管理", href: "/admin/skills", icon: "✺", description: "管理平台级教学 Skill。" },
  { id: "mcp", label: "MCP 管理", href: "/admin/mcp", icon: "⌘", description: "审批和限制外部工具。" },
  { id: "moderation", label: "安全审核", href: "/admin/moderation", icon: "✓", description: "配置内容审核和资源白名单。" },
  { id: "audit", label: "审计日志", href: "/admin/audit", icon: "≋", description: "查看关键操作和安全事件。" },
  { id: "operations", label: "系统运维", href: "/admin/operations", icon: "⚙", description: "查看服务、队列和备份状态。" },
  { id: "showcase", label: "作品展配置", href: "/admin/showcase", icon: "✦", description: "配置首页学生作品墙的行列、排序和审核规则。" },
];
