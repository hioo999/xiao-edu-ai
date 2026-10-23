import { AdminShell } from "../components/admin-shell";
import { ToolManager } from "../components/tool-manager";
export default function McpAdminPage() { return <AdminShell active="/admin/mcp"><ToolManager kind="mcp" title="MCP 管理" /></AdminShell>; }
