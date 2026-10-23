import { apiUrl, type HtmlGeneration, type SelectableTextModel } from "./api-client";

export async function creationRequest<T>(token: string, path: string, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { method, headers: { Authorization: `Bearer ${token}`, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
  } catch { throw new Error("连接不上创作服务，请稍后重试或告诉老师。"); }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: unknown };
    throw new Error(response.status === 401 ? "登录已过期，请重新登录。" : typeof payload.detail === "string" ? payload.detail : "操作没有完成，请稍后重试。");
  }
  return await response.json() as T;
}

export type HtmlVersionSummary = { versionId: string; title: string; teachingSteps: string[] };
export type HtmlWorkspaceProject = HtmlGeneration & { currentVersionId?: string; versions?: HtmlVersionSummary[] };
export type AgentSettings = { capability: "text" | "html" | "image" | "music" | "video"; skillIds: string[]; mcpIds: string[]; knowledgeIds: string[]; runtime: "gateway" | "agentscope" };
export const defaultAgentSettings: AgentSettings = { capability: "text", skillIds: [], mcpIds: [], knowledgeIds: [], runtime: "gateway" };
export type AgentMessage = { role: "student" | "assistant"; text: string; capability?: string; html?: string; jobId?: string | null; assetId?: string | null };
export type AgentConversation = { sessionId: string; agentId: string; title: string; createdAt: string; messages: AgentMessage[] };
export type AgentOptions = { skills: { id: string; name: string }[]; mcp: { id: string; name: string }[]; knowledge: { id: string; name: string }[]; runtimes: string[]; models: SelectableTextModel[] };

export async function listAgentConversations(token: string, agentId: string) {
  return (await creationRequest<{ sessions: AgentConversation[] }>(token, `/student-agents/${encodeURIComponent(agentId)}/sessions`)).sessions;
}
