import { AdminShell } from "../components/admin-shell";
import { KnowledgeManager } from "../components/tool-manager";
export default function KnowledgeAdminPage() { return <AdminShell active="/admin/knowledge"><KnowledgeManager /></AdminShell>; }
