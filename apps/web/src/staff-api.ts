import { apiUrl } from "./api-client.ts";


export interface StaffHandoverPlan { sourceUserId: string; classIds: string[]; courseIds: string[]; }
export interface StaffHandover extends StaffHandoverPlan { handoverId: string; replacementUserId: string; actorId: string; reason: string; createdAt: string; sourceDisabled: boolean; }

async function staffRequest<Result>(token: string, organization: string, username: string, action: string, method = "GET", body?: object): Promise<Result> {
  let response: Response;
  try {
    response = await fetch(apiUrl(`/organizations/${encodeURIComponent(organization)}/staff/${encodeURIComponent(username)}/${action}`), {
      method, cache: "no-store", headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch { throw new Error("账号服务连接失败，请检查后端服务后重试。"); }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : "";
    if (response.status === 401) throw new Error("登录已失效，请重新登录管理员账号。");
    if (response.status === 403) throw new Error("没有管理该账号的权限。");
    if (response.status === 404) throw new Error("账号不存在或不属于当前机构。");
    if (response.status === 409) throw new Error(detail.includes("own account") ? "不能对自己的管理账号执行此操作。" : detail.includes("no teaching resources") ? "该教师没有需要交接的班级或课程。" : "该教师仍有关联班级或课程，请先完成交接。");
    if (response.status === 422) throw new Error("请检查密码、有效期及接任教师；接任教师必须是本机构的有效教师。");
    throw new Error("操作未能完成，请刷新账号状态后重试。");
  }
  return response.json() as Promise<Result>;
}

export function getStaffHandoverPlan(token: string, organization: string, username: string) { return staffRequest<StaffHandoverPlan>(token, organization, username, "handover-plan"); }
export async function listStaffHandovers(token: string, organization: string, username: string) { return (await staffRequest<{ handovers: StaffHandover[] }>(token, organization, username, "handover-history")).handovers; }
export function resetStaffPassword(token: string, organization: string, username: string, password: string) { return staffRequest(token, organization, username, "reset-password", "POST", { password }); }
export function setStaffEnabled(token: string, organization: string, username: string, enabled: boolean) { return staffRequest(token, organization, username, "state", "PUT", { enabled }); }
export function setStaffExpiry(token: string, organization: string, username: string, expiresAt: string | null) { return staffRequest(token, organization, username, "expiry", "PUT", { expiresAt }); }
export function revokeStaffSessions(token: string, organization: string, username: string) { return staffRequest(token, organization, username, "revoke-sessions", "POST"); }
export function handoverStaff(token: string, organization: string, username: string, replacementUserId: string, reason: string) { return staffRequest<StaffHandover>(token, organization, username, "handover", "POST", { replacementUserId, reason }); }
