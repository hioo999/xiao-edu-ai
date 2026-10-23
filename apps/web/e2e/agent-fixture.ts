import type { Page } from "@playwright/test";

export async function mockAgentWorkspace(page: Page, reply = "月球花园里，小兔子勇敢地种下第一朵彩虹花。") {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  await page.route("**/settings/student-access", (route) => route.fulfill({ json: { enabled: true, displayName: "星芽", maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "popular", showcaseKind: "all" } }));
  let profile: Record<string, string> | null = null;
  let configuration = { capability: "text", skillIds: [], mcpIds: [], knowledgeIds: [], runtime: "gateway" };
  const conversations: { sessionId: string; agentId: string; title: string; createdAt: string; messages: Record<string, unknown>[] }[] = [];
  await page.route("**/agents/mine*", async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { agents: profile ? [profile] : [] } });
    profile = { ...route.request().postDataJSON(), agentId: "agent-1" };
    return route.fulfill({ json: profile });
  });
  await page.route("**/agents/mine/agent-1", async (route) => { profile = { ...route.request().postDataJSON(), agentId: "agent-1" }; return route.fulfill({ json: profile }); });
  await page.route("**/student-agents/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/options")) return route.fulfill({ json: { skills: [{ id: "story", name: "故事规则" }], mcp: [], knowledge: [], runtimes: ["gateway"], models: [{ providerId: "deepseek-class", modelId: "deepseek-chat", name: "DeepSeek 聊天模型", providerKind: "deepseek" }] } });
    if (path.endsWith("/settings")) {
      if (route.request().method() === "PUT") configuration = route.request().postDataJSON();
      return route.fulfill({ json: configuration });
    }
    if (path.endsWith("/sessions")) {
      if (route.request().method() === "GET") return route.fulfill({ json: { sessions: conversations } });
      const session = { sessionId: "chat-" + (conversations.length + 1), agentId: "agent-1", title: "新对话", createdAt: new Date().toISOString(), messages: [] };
      conversations.push(session); return route.fulfill({ json: session });
    }
    const sessionId = path.split("/")[3];
    const conversation = conversations.find((item) => item.sessionId === sessionId)!;
    if (path.endsWith("/messages")) {
      const question = route.request().postDataJSON().text;
      const answer = { role: "assistant", text: configuration.capability === "html" ? "网页已生成并保存。" : reply, capability: configuration.capability, html: configuration.capability === "html" ? '<html><body><button onclick="this.textContent=\'找到星星\'">探索</button></body></html>' : "", jobId: ["video", "music", "image"].includes(configuration.capability) ? "job-1" : null, assetId: "agent-work" };
      conversation.messages.push({ role: "student", text: question }, answer); conversation.title = question;
      return route.fulfill({ json: { conversation, message: answer } });
    }
    return route.fulfill({ json: conversation });
  });
  return { getProfile: () => profile, getSettings: () => configuration, conversations };
}
