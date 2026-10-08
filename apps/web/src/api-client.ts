export type PlatformRole = "platform_admin" | "organization_admin" | "teacher" | "student";

export interface PlatformSession {
  userId: string;
  organizationId: string;
  role: PlatformRole;
  accessToken: string;
  expiresAt: string;
}

export interface LoginResponse extends PlatformSession {}
export interface TextGeneration { content: string; providerId: string; modelId: string; }
export interface MediaJob { jobId: string; state: string; statusUrl: string; }
export interface MediaJobStatus { jobId: string; kind: string; state: string; providerId: string | null; assetId: string | null; error: string | null; attempts: number; progress: number; }
export interface MediaOperation { jobId: string; kind: string; ownerUserId: string; state: string; providerId: string | null; progress: number; assetId: string | null; error: string | null; attempts: number; }
export interface HtmlGeneration { projectId: string; assetId?: string | null; currentVersion: { versionId: string; title: string; html: string; teachingSteps: string[]; }; }
export interface InspirationCase { caseId: string; title: string; gradeRange: number[]; interests: string[]; difficulty: string; durationMinutes: number; prompt: string; capability: "text" | "html" | "image" | "music" | "video"; favorite: boolean; attachmentId: string; attachmentFilename: string; }
export interface ProviderSummary { provider_id: string; capability: string; region: string; priority: number; enabled: boolean; api_key: string; provider_kind: string; model_id: string; base_url: string; model_catalog: string[]; }
export interface CourseMaterial { materialId: string; courseId?: string; filename: string; contentType: string; size: number; }
export interface ManagedCourse { courseId: string; title: string; summary: string; blocks: { kind: string; content: string; authoredBy: string }[]; teacherScript: string; promptExamples: string[]; studentFlow: string[]; published: boolean; }

const sessionStorageKey = "ai-workbench-session";

export function apiUrl(path: string, baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"): string {
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

export function resolveWorkMediaUrl(url: string): string {
  return url.startsWith("/works/") ? apiUrl(url) : url;
}

export function sessionFromLoginResponse(response: LoginResponse): PlatformSession {
  return { userId: response.userId, organizationId: response.organizationId, role: response.role, accessToken: response.accessToken, expiresAt: response.expiresAt };
}

export function textGenerationFromResponse(response: TextGeneration): TextGeneration {
  return { content: response.content, providerId: response.providerId, modelId: response.modelId };
}

export async function login(username: string, password: string): Promise<PlatformSession> {
  const response = await fetch(apiUrl("/auth/login"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
  if (!response.ok) throw new Error(response.status === 401 ? "账号或密码不正确，请向老师确认。" : "暂时无法登录，请稍后再试。");
  return sessionFromLoginResponse(await response.json() as LoginResponse);
}

export async function currentUser(accessToken: string): Promise<{ userId: string; organizationId: string; role: PlatformRole; classId: string | null }> {
  const response = await fetch(apiUrl("/auth/me"), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("登录状态已失效");
  return await response.json() as { userId: string; organizationId: string; role: PlatformRole; classId: string | null };
}

export async function bootstrapAdmin(username: string, password: string, organizationId: string): Promise<PlatformSession> {
  const response = await fetch(apiUrl("/auth/bootstrap-admin"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password, organizationId }) });
  if (!response.ok) throw new Error(response.status === 409 ? "管理员账号已经初始化，请直接登录。" : "初始化失败，请检查账号、密码和机构编号。");
  return sessionFromLoginResponse(await response.json() as LoginResponse);
}

export function saveSession(session: PlatformSession): void {
  window.localStorage.setItem(sessionStorageKey, JSON.stringify(session));
  window.sessionStorage.removeItem(sessionStorageKey);
}

export function currentSession(): PlatformSession | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(sessionStorageKey) ?? window.sessionStorage.getItem(sessionStorageKey);
  if (!stored) return null;
  try {
    const session = JSON.parse(stored) as PlatformSession;
    if (!session.accessToken || !session.expiresAt || new Date(session.expiresAt).getTime() <= Date.now()) {
      clearSession();
      return null;
    }
    window.localStorage.setItem(sessionStorageKey, JSON.stringify(session));
    window.sessionStorage.removeItem(sessionStorageKey);
    return session;
  } catch {
    clearSession();
    return null;
  }
}

export function clearSession(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(sessionStorageKey);
    window.sessionStorage.removeItem(sessionStorageKey);
  }
}

async function platformRequest<T>(path: string, accessToken: string, body: object, method = "POST"): Promise<T> {
  const response = await fetch(apiUrl(path), { method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(body) });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail === "no text model is configured" ? "老师还没有开启文字模型，请稍后再试。" : "创作服务暂时不可用，请稍后再试。");
  }
  return await response.json() as T;
}

export async function generateText(accessToken: string, prompt: string): Promise<TextGeneration> {
  return textGenerationFromResponse(await platformRequest<TextGeneration>("/models/text/generate", accessToken, { prompt }));
}
export interface PromptPolishPolicy { capability: "text" | "html" | "image" | "music" | "video"; name: string; instruction: string; enabled: boolean; }
export async function polishPrompt(accessToken: string, capability: PromptPolishPolicy["capability"], content: string): Promise<TextGeneration> { return textGenerationFromResponse(await platformRequest<TextGeneration>("/prompt-polish", accessToken, { capability, content })); }
export async function listPromptPolishPolicies(accessToken: string): Promise<PromptPolishPolicy[]> { const response = await fetch(apiUrl("/prompt-polish/policies"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取润色策略"); return (await response.json() as { policies: PromptPolishPolicy[] }).policies; }
export async function savePromptPolishPolicy(accessToken: string, capability: PromptPolishPolicy["capability"], policy: Pick<PromptPolishPolicy, "instruction" | "enabled">): Promise<PromptPolishPolicy> { const response = await fetch(apiUrl(`/prompt-polish/policies/${capability}`), { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(policy) }); if (!response.ok) throw new Error("保存润色策略失败"); return await response.json() as PromptPolishPolicy; }

export async function createMediaJob(accessToken: string, kind: "image" | "music" | "video", prompt: string, referenceImageUrl?: string): Promise<MediaJob> {
  return await platformRequest<MediaJob>("/media/jobs", accessToken, { kind, prompt, ...(referenceImageUrl ? { referenceImageUrl } : {}) });
}
export async function uploadReferenceImage(accessToken: string, file: File): Promise<string> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(apiUrl("/media/jobs/reference-images"), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body });
  if (!response.ok) throw new Error("参考图需为 5MB 以内的 PNG、JPG 或 WEBP 文件。");
  return (await response.json() as { referenceImageUrl: string }).referenceImageUrl;
}

export async function getMediaJob(accessToken: string, jobId: string): Promise<MediaJobStatus> {
  const response = await fetch(apiUrl(`/media/jobs/${encodeURIComponent(jobId)}`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取创作任务状态");
  return await response.json() as MediaJobStatus;
}
export async function listMediaOperations(accessToken: string, filters: { state?: string; kind?: string } = {}): Promise<MediaOperation[]> { const query = new URLSearchParams({ ...(filters.state ? { state: filters.state } : {}), ...(filters.kind ? { kind: filters.kind } : {}) }); const response = await fetch(apiUrl(`/media/jobs/operations?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取生成任务"); return (await response.json() as { jobs: MediaOperation[] }).jobs; }
export async function retryMediaOperation(accessToken: string, jobId: string): Promise<void> { const response = await fetch(apiUrl(`/media/jobs/${encodeURIComponent(jobId)}/operations/retry`), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) { const payload = await response.json().catch(() => null) as { detail?: string } | null; throw new Error(payload?.detail ?? "任务重试失败"); } }

export async function generateHtml(accessToken: string, projectId: string, prompt: string): Promise<HtmlGeneration> {
  return await platformRequest<HtmlGeneration>(`/projects/${encodeURIComponent(projectId)}/html/generate`, accessToken, { prompt });
}

export async function listInspirationCases(accessToken: string, grade = 4, interests: string[] = []): Promise<InspirationCase[]> {
  const query = new URLSearchParams({ grade: String(grade), ...(interests.length ? { interests: interests.join(",") } : {}) });
  const response = await fetch(apiUrl(`/inspiration?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取灵感案例");
  return (await response.json() as { cases: InspirationCase[] }).cases;
}

export async function favoriteInspirationCase(accessToken: string, caseId: string, enabled: boolean): Promise<void> {
  await platformRequest(`/inspiration/${encodeURIComponent(caseId)}/favorite`, accessToken, { enabled });
}
export async function importInspirationCase(accessToken: string, input: { title: string; prompt: string; capability: InspirationCase["capability"]; gradeMin: number; gradeMax: number; difficulty: string; durationMinutes: number; interests: string; file?: File }): Promise<InspirationCase> {
  const body = new FormData();
  Object.entries(input).forEach(([key, value]) => { if (key !== "file" && value !== undefined) body.append(key.replace(/[A-Z]/g, (match) => `_${match.toLowerCase()}`), String(value)); });
  if (input.file) body.append("file", input.file);
  const response = await fetch(apiUrl("/inspiration/import"), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body });
  if (!response.ok) throw new Error("灵感素材上传失败");
  return await response.json() as InspirationCase;
}
export function inspirationAttachmentUrl(caseId: string): string { return apiUrl(`/inspiration/${encodeURIComponent(caseId)}/attachment`); }

export async function listProviders(accessToken: string): Promise<ProviderSummary[]> {
  const response = await fetch(apiUrl("/models/providers"), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取模型配置");
  return (await response.json() as { providers: ProviderSummary[] }).providers;
}

export async function registerProvider(accessToken: string, provider: { providerId: string; capability: string; region: string; apiKey?: string; providerKind?: string; modelId?: string; baseUrl?: string; priority?: number; enabled?: boolean; modelCatalog?: string[] }): Promise<{ providerId: string; status: string }> {
  return await platformRequest<{ providerId: string; status: string }>("/models/providers", accessToken, provider);
}

export async function deleteProvider(accessToken: string, providerId: string): Promise<{ providerId: string; status: string }> {
  const response = await fetch(apiUrl(`/models/providers/${encodeURIComponent(providerId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("删除模型配置失败");
  return await response.json() as { providerId: string; status: string };
}

export async function testProvider(accessToken: string, providerId: string): Promise<{ providerId: string; status: string; message: string }> {
  const response = await fetch(apiUrl(`/models/providers/${encodeURIComponent(providerId)}/test`), { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: "{}" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "连接测试失败。");
  }
  return await response.json() as { providerId: string; status: string; message: string };
}

export interface AvailableProviderModel { id: string; name: string; }
export async function listAvailableProviderModels(accessToken: string, providerId: string): Promise<AvailableProviderModel[]> {
  const response = await fetch(apiUrl(`/models/providers/${encodeURIComponent(providerId)}/available-models`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("暂时无法从服务商获取最新模型列表");
  return (await response.json() as { models: AvailableProviderModel[] }).models;
}

export interface CreativeWork { assetId: string; projectId: string; ownerUserId: string; kind: string; title: string; previewUrl: string; prompt: string; reviewState: string; featured: boolean; coverUrl: string; processSteps: string[]; gradeMin: number; gradeMax: number; visibility: "organization" | "private"; isExample: boolean; }
export interface WorkComment { commentId: string; authorUserId: string; authorRole: string; body: string; createdAt: string; }
export interface WorkDeployment { deploymentId: string; assetId: string; projectType: string; state: string; manifest: { fileCount: number; projectType: string; entrypoints: string[]; dependencies: string[]; envTemplate: Record<string, string>; hasDatabaseHint: boolean; topLevelDirs: string[] }; envTemplate: Record<string, string>; createdAt: string; updatedAt: string; publishedUrl: string; }
export async function createWork(accessToken: string, work: { projectId: string; kind: "text" | "image" | "music" | "video" | "webpage" | "lesson" | "report"; title: string; previewUrl?: string; prompt?: string }): Promise<CreativeWork> { return await platformRequest<CreativeWork>("/works", accessToken, work); }
export async function uploadExternalWork(accessToken: string, file: File, title = "", ownerUserId = ""): Promise<CreativeWork & { artifact: { filename: string; contentType: string; size: number }; uploadMode: "static_html" | "deployment_package"; deployment: WorkDeployment | null }> {
  const body = new FormData();
  body.append("file", file);
  if (title.trim()) body.append("title", title.trim());
  if (ownerUserId.trim()) body.append("ownerUserId", ownerUserId.trim());
  const response = await fetch(apiUrl("/works/upload"), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body });
  if (!response.ok) { const payload = await response.json().catch(() => null) as { detail?: string } | null; throw new Error(payload?.detail ?? "作品上传失败"); }
  return await response.json() as CreativeWork & { artifact: { filename: string; contentType: string; size: number }; uploadMode: "static_html" | "deployment_package"; deployment: WorkDeployment | null };
}
export async function prepareWorkDeployment(accessToken: string, assetId: string): Promise<WorkDeployment> { return await platformRequest<WorkDeployment>(`/works/${encodeURIComponent(assetId)}/deployments/prepare`, accessToken, {}); }
export async function listWorkDeployments(accessToken: string, assetId: string): Promise<WorkDeployment[]> { const response = await fetch(apiUrl(`/works/${encodeURIComponent(assetId)}/deployments`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取部署记录"); return (await response.json() as { deployments: WorkDeployment[] }).deployments; }
export async function publishWorkDeployment(accessToken: string, assetId: string, deploymentId: string, previewUrl: string): Promise<{ deployment: WorkDeployment; work: CreativeWork }> { return await platformRequest<{ deployment: WorkDeployment; work: CreativeWork }>(`/works/${encodeURIComponent(assetId)}/deployments/${encodeURIComponent(deploymentId)}/publish`, accessToken, { previewUrl }, "PUT"); }
export async function listReviewWorks(accessToken: string, filters: { kind?: string; reviewState?: string; featured?: boolean; search?: string } = {}): Promise<CreativeWork[]> { const query = new URLSearchParams(); if (filters.kind) query.set("kind", filters.kind); if (filters.reviewState) query.set("reviewState", filters.reviewState); if (filters.featured !== undefined) query.set("featured", String(filters.featured)); if (filters.search) query.set("search", filters.search); const response = await fetch(apiUrl(`/works/review?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取作品审核列表"); return (await response.json() as { works: CreativeWork[] }).works; }
export async function listShowcaseWorks(accessToken: string, kind?: string, limit = 24, sort: "featured" | "newest" | "popular" = "featured"): Promise<CreativeWork[]> { const query = new URLSearchParams({ limit: String(limit), sort, ...(kind && kind !== "all" ? { kind } : {}) }); const response = await fetch(apiUrl(`/works/showcase?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取作品展示"); return (await response.json() as { works: CreativeWork[] }).works; }
export async function reviewWork(accessToken: string, assetId: string, state: "pending" | "approved" | "rejected", featured: boolean): Promise<CreativeWork> { return await platformRequest<CreativeWork>(`/works/${encodeURIComponent(assetId)}/review`, accessToken, { state, featured }); }
export async function updateWorkMetadata(accessToken: string, assetId: string, metadata: { title?: string; previewUrl?: string; coverUrl?: string; processSteps?: string[]; gradeMin?: number; gradeMax?: number; visibility?: "organization" | "private"; isExample?: boolean }): Promise<CreativeWork> { return await platformRequest<CreativeWork>(`/works/${encodeURIComponent(assetId)}/metadata`, accessToken, metadata, "PUT"); }
export async function uploadWorkMedia(accessToken: string, assetId: string, slot: "cover" | "preview", file: File): Promise<{ work: CreativeWork; media: { slot: string; filename: string; contentType: string; size: number; url: string } }> { const body = new FormData(); body.append("file", file); const response = await fetch(apiUrl(`/works/${encodeURIComponent(assetId)}/media/${slot}`), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body }); if (!response.ok) { const payload = await response.json().catch(() => null) as { detail?: string } | null; throw new Error(payload?.detail ?? "作品媒体上传失败"); } return await response.json() as { work: CreativeWork; media: { slot: string; filename: string; contentType: string; size: number; url: string } }; }
export async function batchReviewWorks(accessToken: string, assetIds: string[], state: "approved" | "rejected", featured: boolean): Promise<{ reviewed: number; works: CreativeWork[] }> { return await platformRequest<{ reviewed: number; works: CreativeWork[] }>("/works/review/batch", accessToken, { assetIds, state, featured }); }
export async function deleteWork(accessToken: string, assetId: string): Promise<void> { const response = await fetch(apiUrl(`/works/${encodeURIComponent(assetId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("删除作品失败"); }
export async function listMyWorks(accessToken: string): Promise<CreativeWork[]> { const response = await fetch(apiUrl("/works/mine"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取我的作品"); return (await response.json() as { works: CreativeWork[] }).works; }
export async function getWork(accessToken: string, assetId: string): Promise<CreativeWork> { const response = await fetch(apiUrl(`/works/${encodeURIComponent(assetId)}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取作品详情"); return await response.json() as CreativeWork; }
export async function getWorkInteractions(accessToken: string, assetId: string): Promise<{ comments: WorkComment[]; likeCount: number; liked: boolean }> { const response = await fetch(apiUrl(`/works/${encodeURIComponent(assetId)}/comments`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取作品互动"); return await response.json() as { comments: WorkComment[]; likeCount: number; liked: boolean }; }
export async function likeWork(accessToken: string, assetId: string, enabled: boolean): Promise<{ liked: boolean; likeCount: number }> { return await platformRequest<{ liked: boolean; likeCount: number }>(`/works/${encodeURIComponent(assetId)}/like`, accessToken, { enabled }); }
export async function commentOnWork(accessToken: string, assetId: string, body: string): Promise<WorkComment> { return await platformRequest<WorkComment>(`/works/${encodeURIComponent(assetId)}/comments`, accessToken, { body }); }
export async function createShare(accessToken: string, assetId: string): Promise<{ token: string; expiresAt: string }> { return await platformRequest(`/shares`, accessToken, { assetId, expiresInHours: 72, allowDownload: false }); }
export async function getPublicShare(token: string): Promise<{ work: CreativeWork; allowDownload: boolean }> {
  const response = await fetch(apiUrl(`/shares/public/${encodeURIComponent(token)}`));
  if (!response.ok) throw new Error("该分享链接已失效或被撤回");
  return await response.json() as { work: CreativeWork; allowDownload: boolean };
}
export interface UsageMetric { metric: string; limit: number; used: number; reserved: number; }
export interface MyUsageMetric extends UsageMetric { scope: string; scopeId: string; remaining: number; }
export async function myUsageSummary(accessToken: string): Promise<MyUsageMetric[]> { const response = await fetch(apiUrl("/usage/mine"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取创作积分"); return (await response.json() as { metrics: MyUsageMetric[] }).metrics; }
export interface ProvisionedStudent { username: string; classId: string; initialPassword: string; }
export async function provisionStudents(accessToken: string, organizationId: string, request: { prefix: string; count: number; classId: string; initialPassword: string; expiresAt?: string | null }): Promise<ProvisionedStudent[]> { return (await platformRequest<{ students: ProvisionedStudent[] }>(`/organizations/${encodeURIComponent(organizationId)}/students/batch`, accessToken, request)).students; }
export interface ManagedStudent { username: string; userId: string; organizationId: string; classId: string | null; enabled: boolean; expired: boolean; expiresAt: string | null; }
export async function listStudents(accessToken: string, organizationId: string, filters: { search?: string; classId?: string; enabled?: boolean; expired?: boolean; offset?: number; limit?: number } = {}): Promise<ManagedStudent[]> {
  const query = new URLSearchParams();
  if (filters.search) query.set("search", filters.search);
  if (filters.classId) query.set("classId", filters.classId);
  if (filters.enabled !== undefined) query.set("enabled", String(filters.enabled));
  if (filters.expired !== undefined) query.set("expired", String(filters.expired));
  if (filters.offset !== undefined) query.set("offset", String(filters.offset));
  if (filters.limit !== undefined) query.set("limit", String(filters.limit));
  const response = await fetch(apiUrl(`/organizations/${encodeURIComponent(organizationId)}/students?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取学生账号");
  return (await response.json() as { students: ManagedStudent[] }).students;
}
export async function setStudentState(accessToken: string, organizationId: string, username: string, enabled: boolean): Promise<void> { const response = await fetch(apiUrl(`/organizations/${encodeURIComponent(organizationId)}/students/${encodeURIComponent(username)}/state`), { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ enabled }) }); if (!response.ok) throw new Error("更新账号状态失败"); }
export async function resetStudentPassword(accessToken: string, organizationId: string, username: string, password: string): Promise<void> { await platformRequest(`/organizations/${encodeURIComponent(organizationId)}/students/${encodeURIComponent(username)}/reset-password`, accessToken, { password }); }
export async function setStudentExpiry(accessToken: string, organizationId: string, username: string, expiresAt: string | null): Promise<void> { await platformRequest(`/organizations/${encodeURIComponent(organizationId)}/students/${encodeURIComponent(username)}/expiry`, accessToken, { expiresAt }); }
export interface ManagedStaff { username: string; userId: string; organizationId: string; role: "teacher" | "organization_admin"; enabled: boolean; expiresAt: string | null; }
export async function listStaff(accessToken: string, organizationId: string): Promise<ManagedStaff[]> { const response = await fetch(apiUrl(`/organizations/${encodeURIComponent(organizationId)}/staff`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取教师与管理员账号"); return (await response.json() as { staff: ManagedStaff[] }).staff; }
export async function createStaff(accessToken: string, organizationId: string, request: { username: string; password: string; role: "teacher" | "organization_admin"; expiresAt?: string | null }): Promise<ManagedStaff> { return await platformRequest<ManagedStaff>(`/organizations/${encodeURIComponent(organizationId)}/staff`, accessToken, request); }
export async function setAccountsState(accessToken: string, organizationId: string, usernames: string[], enabled: boolean): Promise<number> { return (await platformRequest<{ changed: number }>(`/organizations/${encodeURIComponent(organizationId)}/accounts/bulk-state`, accessToken, { usernames, enabled })).changed; }
export async function setAccountsExpiry(accessToken: string, organizationId: string, usernames: string[], expiresAt: string | null): Promise<number> { return (await platformRequest<{ changed: number }>(`/organizations/${encodeURIComponent(organizationId)}/accounts/bulk-expiry`, accessToken, { usernames, expiresAt })).changed; }
export interface AuditRecord { record_id: number; organization_id: string; actor_id: string; action: string; target_type: string; target_id: string; created_at: string; }
export async function platformReadiness(): Promise<{ status: string; storage: string }> { const response = await fetch(apiUrl("/health/ready")); if (!response.ok) throw new Error("平台存储暂不可用"); return await response.json() as { status: string; storage: string }; }
export async function listAuditRecords(accessToken: string, filters: { offset?: number; actorId?: string; action?: string; targetType?: string; since?: string; until?: string } = {}): Promise<AuditRecord[]> { const query = new URLSearchParams({ limit: "100", ...(filters.offset !== undefined ? { offset: String(filters.offset) } : {}), ...(filters.actorId ? { actorId: filters.actorId } : {}), ...(filters.action ? { action: filters.action } : {}), ...(filters.targetType ? { targetType: filters.targetType } : {}), ...(filters.since ? { since: filters.since } : {}), ...(filters.until ? { until: filters.until } : {}) }); const response = await fetch(apiUrl(`/audit?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取审计记录"); return (await response.json() as { records: AuditRecord[] }).records; }
export async function exportAuditRecords(accessToken: string): Promise<Blob> { const response = await fetch(apiUrl("/audit/export.csv"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("导出审计记录失败"); return await response.blob(); }
export async function usageSummary(accessToken: string, scope = "organization", scopeId?: string): Promise<UsageMetric[]> { const query = new URLSearchParams({ scope, ...(scopeId ? { scope_id: scopeId } : {}) }); const response = await fetch(apiUrl(`/usage/summary?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取额度统计"); return (await response.json() as { metrics: UsageMetric[] }).metrics; }
export async function setUsageLimit(accessToken: string, metric: "text" | "image" | "video" | "music" | "storage", limit: number, scope = "organization", scopeId?: string): Promise<void> { await platformRequest("/usage/limits", accessToken, { metric, limit, scope, ...(scopeId ? { scopeId } : {}) }); }
export async function modelCallSummary(accessToken: string): Promise<{ providerId: string; capability: string; outcome: string; count: number }[]> { const response = await fetch(apiUrl("/models/calls/summary"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取调用日志"); return (await response.json() as { calls: { providerId: string; capability: string; outcome: string; count: number }[] }).calls; }
export interface ModelCallRecord { organization_id: string; provider_id: string; capability: string; outcome: string; created_at: string; }
export async function listModelCalls(accessToken: string, filters: { offset?: number; providerId?: string; capability?: string; outcome?: string } = {}): Promise<ModelCallRecord[]> { const query = new URLSearchParams({ ...(filters.offset !== undefined ? { offset: String(filters.offset) } : {}), ...(filters.providerId ? { providerId: filters.providerId } : {}), ...(filters.capability ? { capability: filters.capability } : {}), ...(filters.outcome ? { outcome: filters.outcome } : {}) }); const response = await fetch(apiUrl(`/models/calls?${query.toString()}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取模型调用记录"); return (await response.json() as { calls: ModelCallRecord[] }).calls; }
export interface KnowledgeDocument { document_id: string; scope: string; scope_id: string; title: string; }
export async function listKnowledge(accessToken: string): Promise<KnowledgeDocument[]> { const response = await fetch(apiUrl("/knowledge"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取知识库"); return (await response.json() as { documents: KnowledgeDocument[] }).documents; }
export async function addKnowledge(accessToken: string, title: string, scope = "organization"): Promise<KnowledgeDocument> { return await platformRequest<KnowledgeDocument>("/knowledge", accessToken, { title, scope }); }
export async function deleteKnowledge(accessToken: string, documentId: string): Promise<void> { const response = await fetch(apiUrl(`/knowledge/${encodeURIComponent(documentId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("删除知识条目失败"); }
export interface ManagedTool { tool_id: string; kind: string; name: string; capabilities: string; enabled: boolean; instruction: string; }
export async function listManagedTools(accessToken: string, kind: "skills" | "mcp"): Promise<ManagedTool[]> { const response = await fetch(apiUrl(`/agents/${kind}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取工具配置"); const payload = await response.json() as { skills?: ManagedTool[]; servers?: ManagedTool[] }; return payload.skills ?? payload.servers ?? []; }
export async function saveManagedTool(accessToken: string, kind: "skills" | "mcp", tool: { toolId: string; name: string; capabilities: string; enabled: boolean; instruction?: string }): Promise<ManagedTool> { return await platformRequest<ManagedTool>(`/agents/${kind}`, accessToken, tool); }
export async function deleteManagedTool(accessToken: string, kind: "skills" | "mcp", toolId: string): Promise<void> { const response = await fetch(apiUrl(`/agents/${kind}/${encodeURIComponent(toolId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("删除工具配置失败"); }
export interface ManagedAgent { agentId: string; name: string; capability: "text" | "image" | "video" | "music" | "html"; gradeRange: string; published: boolean; }
export async function listAgents(accessToken: string): Promise<ManagedAgent[]> { const response = await fetch(apiUrl("/agents"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取智能体列表"); return (await response.json() as { agents: ManagedAgent[] }).agents; }
export async function dispatchAgent(accessToken: string, payload: { agentId: string; prompt: string }): Promise<{ agentId: string; status: string; message: string }> { return await platformRequest<{ agentId: string; status: string; message: string }>("/agents/dispatch", accessToken, { ...payload, classroomOpen: true, featureEnabled: true, quotaAvailable: true, modelAvailable: true, modelRegion: "domestic", mcpApproved: true }); }
export async function saveAgent(accessToken: string, agent: ManagedAgent): Promise<ManagedAgent> { return await platformRequest<ManagedAgent>("/agents", accessToken, agent); }
export async function deleteAgent(accessToken: string, agentId: string): Promise<void> { const response = await fetch(apiUrl(`/agents/${encodeURIComponent(agentId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("删除智能体失败"); }

export async function uploadCourseMaterial(accessToken: string, courseId: string, file: File): Promise<CourseMaterial> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(apiUrl(`/courses/${encodeURIComponent(courseId)}/materials`), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body });
  if (!response.ok) throw new Error("课件上传失败，请稍后再试。");
  return await response.json() as CourseMaterial;
}

export async function listCourses(accessToken: string): Promise<ManagedCourse[]> {
  const response = await fetch(apiUrl("/courses"), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取课程列表");
  return (await response.json() as { courses: ManagedCourse[] }).courses;
}

export async function getCourse(accessToken: string, courseId: string): Promise<ManagedCourse> {
  const response = await fetch(apiUrl(`/courses/${encodeURIComponent(courseId)}`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取课程内容");
  return await response.json() as ManagedCourse;
}

export async function saveCourse(accessToken: string, course: ManagedCourse): Promise<ManagedCourse> {
  return await platformRequest<ManagedCourse>("/courses", accessToken, course);
}

export async function listCourseMaterials(accessToken: string, courseId: string): Promise<CourseMaterial[]> {
  const response = await fetch(apiUrl(`/courses/${encodeURIComponent(courseId)}/materials`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取课件资源");
  return (await response.json() as { materials: CourseMaterial[] }).materials;
}
export async function listStudentCourses(accessToken: string, classId: string): Promise<ManagedCourse[]> {
  const response = await fetch(apiUrl(`/courses/classrooms/${encodeURIComponent(classId)}/published`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取已发布课程");
  return (await response.json() as { courses: ManagedCourse[] }).courses;
}
export async function listStudentCourseMaterials(accessToken: string, classId: string, courseId: string): Promise<CourseMaterial[]> {
  const response = await fetch(apiUrl(`/courses/classrooms/${encodeURIComponent(classId)}/published/${encodeURIComponent(courseId)}/materials`), { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!response.ok) throw new Error("无法读取课程课件");
  return (await response.json() as { materials: CourseMaterial[] }).materials;
}
export function courseMaterialDownloadUrl(materialId: string): string { return apiUrl(`/courses/materials/${encodeURIComponent(materialId)}/download`); }
export async function publishCourse(accessToken: string, courseId: string, classId: string): Promise<void> { await platformRequest(`/courses/${encodeURIComponent(courseId)}/publish`, accessToken, { classId }); }
export async function unpublishCourse(accessToken: string, courseId: string, classId: string): Promise<void> { await platformRequest(`/courses/${encodeURIComponent(courseId)}/unpublish`, accessToken, { classId }); }
export async function deleteCourse(accessToken: string, courseId: string): Promise<void> { const response = await fetch(apiUrl(`/courses/${encodeURIComponent(courseId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("删除课程失败"); }
export async function deleteCourseMaterial(accessToken: string, materialId: string): Promise<void> { const response = await fetch(apiUrl(`/courses/materials/${encodeURIComponent(materialId)}`), { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("删除课件失败"); }

export interface LearningProgress { studentId: string; courseId: string; percent: number; completed: boolean; lastBlockIndex: number; updatedAt: string; }
export interface HomeworkSubmission { submissionId: string; studentId: string; courseId: string; content: string; status: "submitted" | "reviewed" | "rejected"; teacherFeedback: string; submittedAt: string; reviewedAt: string; }
export async function upsertLearningProgress(accessToken: string, courseId: string, progress: { percent: number; completed: boolean; lastBlockIndex: number }): Promise<LearningProgress> { return await platformRequest<LearningProgress>(`/learning/progress/${encodeURIComponent(courseId)}`, accessToken, progress, "PUT"); }
export async function listMyLearningProgress(accessToken: string): Promise<LearningProgress[]> { const response = await fetch(apiUrl("/learning/me/progress"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取学习进度"); return (await response.json() as { progress: LearningProgress[] }).progress; }
export async function submitHomework(accessToken: string, courseId: string, content: string): Promise<HomeworkSubmission> { return await platformRequest<HomeworkSubmission>(`/learning/courses/${encodeURIComponent(courseId)}/submissions`, accessToken, { content }); }
export async function listMyHomework(accessToken: string): Promise<HomeworkSubmission[]> { const response = await fetch(apiUrl("/learning/me/submissions"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取作业"); return (await response.json() as { submissions: HomeworkSubmission[] }).submissions; }
export async function listCourseLearningProgress(accessToken: string, courseId: string): Promise<LearningProgress[]> { const response = await fetch(apiUrl(`/learning/courses/${encodeURIComponent(courseId)}/progress`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取课程进度"); return (await response.json() as { progress: LearningProgress[] }).progress; }
export async function listCourseHomework(accessToken: string, courseId: string): Promise<HomeworkSubmission[]> { const response = await fetch(apiUrl(`/learning/courses/${encodeURIComponent(courseId)}/submissions`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取作业提交"); return (await response.json() as { submissions: HomeworkSubmission[] }).submissions; }
export async function annotateHomework(accessToken: string, submissionId: string, feedback: string, status: "reviewed" | "rejected" = "reviewed"): Promise<HomeworkSubmission> { return await platformRequest<HomeworkSubmission>(`/learning/submissions/${encodeURIComponent(submissionId)}/annotate`, accessToken, { feedback, status }); }

export interface ClassroomStudent { studentId: string; activeFeature: string; taskState: string; lessonStep: number; helpNeeded: boolean; assistanceGranted: boolean; }
export interface ManagedClassroom { classId: string; state: "open" | "paused" | "closed"; teacherCount: number; onlineStudents: number; helpNeeded: number; }
export interface ClassroomSchedule { startDate: string; endDate: string; weekdays: number[]; dailyWindows: { start: string; end: string }[]; holidayExceptions?: string[]; }
export async function classroomRequest<T>(path: string, accessToken: string, method = "POST", body?: object): Promise<T> {
  const response = await fetch(apiUrl(path), { method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, ...(body ? { body: JSON.stringify(body) } : {}) });
  if (!response.ok) throw new Error("课堂操作失败");
  return await response.json() as T;
}
export async function listClassroomStudents(accessToken: string, classId: string): Promise<ClassroomStudent[]> { return (await classroomRequest<{ students: ClassroomStudent[] }>(`/classrooms/${encodeURIComponent(classId)}/students`, accessToken, "GET")).students; }
export interface StudentView { classId: string; studentId: string; mode: string; readOnly: boolean; activeFeature: string; taskState: string; lessonStep: number; helpNeeded: boolean; }
export async function getStudentClassroomView(accessToken: string, classId: string, studentId: string): Promise<StudentView> { return await classroomRequest<StudentView>(`/classrooms/${encodeURIComponent(classId)}/students/${encodeURIComponent(studentId)}/view`, accessToken, "GET"); }
export async function assistStudent(accessToken: string, classId: string, studentId: string): Promise<void> { await classroomRequest(`/classrooms/${encodeURIComponent(classId)}/assistance`, accessToken, "POST", { studentId }); }
export async function listClassrooms(accessToken: string): Promise<ManagedClassroom[]> { return (await classroomRequest<{ classrooms: ManagedClassroom[] }>("/classrooms", accessToken, "GET")).classrooms; }
export async function createClassroom(accessToken: string, classId: string): Promise<{ classId: string; state: string }> { return await classroomRequest<{ classId: string; state: string }>("/classrooms", accessToken, "POST", { classId }); }
export async function setClassroomState(accessToken: string, classId: string, state: "open" | "paused" | "closed"): Promise<void> { await classroomRequest(`/classrooms/${encodeURIComponent(classId)}/${state === "closed" ? "close" : state === "open" ? "open" : "pause"}`, accessToken); }
export async function assignClassroomTeachers(accessToken: string, classId: string, teacherIds: string[]): Promise<void> { await classroomRequest(`/classrooms/${encodeURIComponent(classId)}/teachers`, accessToken, "PUT", { teacherIds }); }
export async function getClassroom(accessToken: string, classId: string): Promise<{ classId: string; state: string; schedule: ClassroomSchedule | null }> { return await classroomRequest(`/classrooms/${encodeURIComponent(classId)}`, accessToken, "GET"); }
export async function saveClassroomSchedule(accessToken: string, classId: string, schedule: ClassroomSchedule): Promise<void> { await classroomRequest(`/classrooms/${encodeURIComponent(classId)}/schedule`, accessToken, "PUT", schedule); }
export interface OrganizationSettings { displayName: string; studentHomeEnabled: boolean; maintenanceMessage: string; showcaseColumns: number; showcaseRows: number; showcaseSort: "featured" | "newest" | "popular"; showcaseKind: "all" | "webpage" | "image" | "music" | "video"; }
export interface StudentAccess { enabled: boolean; displayName: string; maintenanceMessage: string; showcaseColumns: number; showcaseRows: number; showcaseSort: "featured" | "newest" | "popular"; showcaseKind: "all" | "webpage" | "image" | "music" | "video"; }
export async function getOrganizationSettings(accessToken: string): Promise<OrganizationSettings> { const response = await fetch(apiUrl("/settings"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取系统设置"); return await response.json() as OrganizationSettings; }
export async function saveOrganizationSettings(accessToken: string, settings: OrganizationSettings): Promise<OrganizationSettings> { const response = await fetch(apiUrl("/settings"), { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(settings) }); if (!response.ok) throw new Error("保存系统设置失败"); return await response.json() as OrganizationSettings; }
export async function revokeOrganizationSessions(accessToken: string): Promise<number> { const response = await fetch(apiUrl("/settings/security/revoke-sessions"), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("强制下线失败"); return (await response.json() as { revoked: number }).revoked; }
export async function getStudentAccess(accessToken: string): Promise<StudentAccess> { const response = await fetch(apiUrl("/settings/student-access"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取学生端状态"); return await response.json() as StudentAccess; }

export function destinationForRole(role: PlatformRole): string {
  if (role === "platform_admin" || role === "organization_admin") return "/admin";
  if (role === "teacher") return "/teacher";
  return "/";
}

export interface LearningReport { studentId: string; completedLessons: string[]; submittedAssignments: string[]; reviewedAssignments: string[]; aiGenerated: boolean; }
export async function myLearningReport(accessToken: string): Promise<LearningReport> { const response = await fetch(apiUrl("/reports/me"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("成长报告还没有生成，请先完成课程或提交作业。"); return await response.json() as LearningReport; }
export async function getStudentLearningReport(accessToken: string, studentId: string): Promise<LearningReport> { const response = await fetch(apiUrl(`/reports/students/${encodeURIComponent(studentId)}`), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("该学生暂时没有成长报告。"); return await response.json() as LearningReport; }
export async function recordLearningEvent(accessToken: string, eventType: string, label: string): Promise<void> { const response = await fetch(apiUrl("/reports/events"), { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ eventType, label }) }); if (!response.ok) throw new Error("学习事件记录失败"); }

export interface ModerationPolicy { enabled: boolean; modes: string[]; status: string; blockedTerms: string[]; }
export async function getModerationPolicy(accessToken: string): Promise<ModerationPolicy> { const response = await fetch(apiUrl("/moderation/policy"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("无法读取安全审核策略"); return await response.json() as ModerationPolicy; }
export async function saveModerationPolicy(accessToken: string, policy: { enabled: boolean; blockedTerms: string[] }): Promise<ModerationPolicy> { const response = await fetch(apiUrl("/moderation/policy"), { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(policy) }); if (!response.ok) throw new Error("保存安全审核策略失败"); return await response.json() as ModerationPolicy; }
export async function checkModerationContent(accessToken: string, content: string, mode = "classroom"): Promise<{ decision: string; mode: string }> { const response = await fetch(apiUrl("/moderation/check"), { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ content, mode }) }); if (!response.ok) return { decision: "blocked", mode }; return await response.json() as { decision: string; mode: string }; }

export interface AgentReadiness { mode: "gateway" | "agentscope"; ready: boolean; reason: string; mcpServers: string[]; checks: { id: string; ready: boolean; detail: string }[]; }
export async function agentReadiness(): Promise<AgentReadiness> { const response = await fetch(apiUrl("/health/agents")); if (!response.ok) throw new Error("无法读取智能体运行时状态"); return await response.json() as AgentReadiness; }
export async function mediaWorkerReadiness(): Promise<{ workerReady: boolean; reason?: string }> { const response = await fetch(apiUrl("/health/media-worker")); if (!response.ok) return { workerReady: false, reason: "生成队列未配置" }; return await response.json() as { workerReady: boolean; reason?: string }; }
export interface DeadLetterJob { jobId: string; kind: string; state: string; error: string | null; attempts: number; }
export async function listDeadLetters(accessToken: string): Promise<DeadLetterJob[]> { const response = await fetch(apiUrl("/media/jobs/operations/dead-letters"), { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) return []; return (await response.json() as { jobs: DeadLetterJob[] }).jobs; }
export async function retryDeadLetter(accessToken: string, jobId: string): Promise<void> { const response = await fetch(apiUrl(`/media/jobs/operations/dead-letters/${encodeURIComponent(jobId)}/retry`), { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error("重试失败任务失败"); }
