import { expect, test } from "@playwright/test";


test("administrator resets a teacher password and completes a confirmed teaching handover", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "admin", organizationId: "school", role: "organization_admin", accessToken: "admin-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  let sourceEnabled = true;
  let reset = false;
  let completed = false;
  let handoverBody: Record<string, string> | null = null;
  const record = { handoverId: "handover-1", sourceUserId: "source-user", replacementUserId: "replacement-user", actorId: "admin", reason: "原教师离职，安排接任", createdAt: "2026-10-19T10:00:00Z", sourceDisabled: true, classIds: ["class-a"], courseIds: ["course-a"] };
  await page.route("**/settings/student-access", route => route.fulfill({ json: { enabled: true, displayName: "星芽" } }));
  await page.route("http://127.0.0.1:8000/organizations/school/students**", route => route.fulfill({ json: { students: [] } }));
  await page.route("http://127.0.0.1:8000/organizations/school/staff", route => route.fulfill({ json: { staff: [
    { username: "source", userId: "source-user", organizationId: "school", role: "teacher", enabled: sourceEnabled, expiresAt: null },
    { username: "replacement", userId: "replacement-user", organizationId: "school", role: "teacher", enabled: true, expiresAt: null },
  ] } }));
  await page.route("http://127.0.0.1:8000/organizations/school/staff/source/handover-plan", route => route.fulfill({ json: { sourceUserId: "source-user", classIds: completed ? [] : ["class-a"], courseIds: completed ? [] : ["course-a"] } }));
  await page.route("http://127.0.0.1:8000/organizations/school/staff/source/handover-history", route => route.fulfill({ json: { handovers: completed ? [record] : [] } }));
  await page.route("http://127.0.0.1:8000/organizations/school/staff/source/reset-password", async route => {
    expect(route.request().headers().authorization).toBe("Bearer admin-token");
    expect(route.request().postDataJSON()).toEqual({ password: "new-password123" });
    reset = true;
    await route.fulfill({ json: { status: "password_reset" } });
  });
  await page.route("http://127.0.0.1:8000/organizations/school/staff/source/handover", async route => {
    handoverBody = route.request().postDataJSON();
    sourceEnabled = false; completed = true;
    await route.fulfill({ json: record });
  });
  await page.goto("/admin/users");
  await page.getByRole("button", { name: "管理 source", exact: true }).click();
  await expect(page.getByText("任教班级：class-a；负责课程：course-a。")).toBeVisible();
  await expect(page.getByRole("button", { name: "停用账号", exact: true })).toBeDisabled();
  await page.getByLabel("新密码（至少 8 位）").fill("new-password123");
  await page.getByRole("button", { name: "重置工作人员密码" }).click();
  await expect(page.getByRole("status").filter({ hasText: "密码已重置" })).toContainText("旧登录会话和课堂协助授权已撤销");
  expect(reset).toBe(true);
  await expect(page.getByLabel("新密码（至少 8 位）")).toHaveValue("");
  await page.getByLabel("接任教师").selectOption("replacement-user");
  await page.getByLabel("交接原因").fill(record.reason);
  await expect(page.getByRole("button", { name: "确认交接并停用" })).toBeDisabled();
  await page.getByLabel(/我已确认移交上述全部班级和课程/).check();
  await page.getByRole("button", { name: "确认交接并停用" }).click();
  await expect(page.getByRole("status").filter({ hasText: "交接已完成" })).toContainText("交接已完成");
  await expect(page.getByRole("button", { name: "启用账号", exact: true })).toBeVisible();
  expect(handoverBody).toEqual({ replacementUserId: "replacement-user", reason: record.reason });
  await expect(page.getByRole("listitem").filter({ hasText: record.reason })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
