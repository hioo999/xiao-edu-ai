import assert from "node:assert/strict";
import test from "node:test";
import { getStaffHandoverPlan, handoverStaff, resetStaffPassword, setStaffEnabled } from "../src/staff-api.ts";


test("staff lifecycle calls dedicated endpoints and never uses student password routes", async () => {
  const originalFetch = globalThis.fetch;
  const requests: { url: string; options: RequestInit | undefined }[] = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), options });
    return new Response(JSON.stringify({ classIds: ["class-a"], courseIds: ["course-a"], sourceDisabled: true }), { headers: { "Content-Type": "application/json" } });
  };
  try {
    const plan = await getStaffHandoverPlan("token", "school", "老师 A");
    await resetStaffPassword("token", "school", "老师 A", "new-password");
    await setStaffEnabled("token", "school", "老师 A", false);
    await handoverStaff("token", "school", "老师 A", "teacher-b", "离职交接");
    assert.deepEqual(plan.classIds, ["class-a"]);
    assert.match(requests[0].url, /\/staff\/%E8%80%81%E5%B8%88%20A\/handover-plan$/);
    assert.match(requests[1].url, /\/staff\/.*\/reset-password$/);
    assert.equal(requests[2].options?.method, "PUT");
    assert.equal(new Headers(requests[3].options?.headers).get("Authorization"), "Bearer token");
    assert.deepEqual(JSON.parse(String(requests[3].options?.body)), { replacementUserId: "teacher-b", reason: "离职交接" });
    assert.ok(requests.every(request => !request.url.includes("/students/")));
  } finally { globalThis.fetch = originalFetch; }
});

test("a blocked teacher disable explains that handover is required", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "teacher has assigned classes or courses; complete handover first" }), { status: 409, headers: { "Content-Type": "application/json" } });
  try {
    await assert.rejects(setStaffEnabled("token", "school", "teacher-a", false), /先完成交接/);
  } finally { globalThis.fetch = originalFetch; }
});
