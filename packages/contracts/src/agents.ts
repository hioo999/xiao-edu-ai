import type { Id, TenantContext } from "./auth.js";

export type AgentKind = "chat" | "html" | "image" | "music" | "video" | "voice" | "expert_team";

export interface AgentRequest {
  requestId: Id;
  tenant: TenantContext;
  agentKind: AgentKind;
  prompt: string;
  projectId?: Id;
}
