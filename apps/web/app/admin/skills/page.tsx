import { AdminShell } from "../components/admin-shell";
import { ToolManager } from "../components/tool-manager";
export default function SkillsAdminPage() { return <AdminShell active="/admin/agents"><ToolManager kind="skills" title="Skill 管理" /></AdminShell>; }
