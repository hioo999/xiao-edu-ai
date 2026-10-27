import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page, role: string, userId: string) {
  await page.addInitScript((value) => window.localStorage.setItem("ai-workbench-session", JSON.stringify(value)), { userId, organizationId: "org-e2e", role, accessToken: `${role}-token`, expiresAt: "2099-01-01T00:00:00.000Z" });
}

test("admin creates and binds a parent", async ({ page }) => {
  await signIn(page, "platform_admin", "admin-e2e");
  await page.route("**/organizations/org-e2e/students?*", (route) => route.fulfill({ json: { students: [{ username: "student-a", userId: "student-a", organizationId: "org-e2e", classId: "class-a", enabled: true, expired: false, expiresAt: null }] } }));
  let created: Record<string, unknown> | null = null;
  let relation: Record<string, unknown> | null = null;
  await page.route("**/parent-portal/parents", (route) => { created = route.request().postDataJSON(); return route.fulfill({ json: { parent_id: "parent-a" } }); });
  await page.route("**/parent-portal/relations", (route) => { relation = route.request().postDataJSON(); return route.fulfill({ json: { parent_id: "parent-a", student_id: "student-a", status: "verified" } }); });
  await page.goto("/admin/parents");
  await expect(page.getByRole("heading", { name: "家长账号" })).toBeVisible();
  await page.getByPlaceholder("例如：李明妈妈").fill("小明妈妈");
  await page.getByPlaceholder("parent-liming").fill("parent-a");
  await page.getByPlaceholder("至少 8 位").fill("example-password");
  await page.getByRole("button", { name: "创建家长账号并绑定" }).click();
  await expect(page.getByText(/家长账号创建并绑定成功/)).toBeVisible();
  expect(created).toMatchObject({ name: "小明妈妈", username: "parent-a" });
  expect(relation).toMatchObject({ parentId: "parent-a", studentId: "student-a" });
});

test("teacher sends a parent notice", async ({ page }) => {
  await signIn(page, "teacher", "teacher-a");
  await page.route("**/organizations/org-e2e/students?*", (route) => route.fulfill({ json: { students: [{ username: "student-a", userId: "student-a", organizationId: "org-e2e", classId: "class-a", enabled: true, expired: false, expiresAt: null }] } }));
  let notice: Record<string, unknown> | null = null;
  await page.route("**/parent-portal/notifications", (route) => { notice = route.request().postDataJSON(); return route.fulfill({ json: { id: "notice-1" } }); });
  await page.goto("/teacher/parents");
  await page.getByRole("checkbox", { name: "作为家长通知发布" }).check();
  await page.getByPlaceholder("例如：本周课程提醒").fill("周五课堂");
  await page.getByPlaceholder("写下具体、积极、可执行的反馈…").fill("请带好画笔");
  await page.getByRole("button", { name: "发布给家长" }).click();
  await expect(page.getByText("家长通知已发布。")).toBeVisible();
  expect(notice).toMatchObject({ studentId: "student-a", title: "周五课堂", content: "请带好画笔" });
});

test("parent sees a bound student's course, feedback and work", async ({ page }) => {
  await signIn(page, "parent", "parent-a");
  await page.route("**/parent-portal/students", (route) => route.fulfill({ json: { students: ["student-a"] } }));
  await page.route("**/parent-portal/students/student-a/overview", (route) => route.fulfill({ json: { studentId: "student-a", progress: [{ courseId: "course-a", title: "海洋创作课", summary: "", lessons: [{ lessonId: "lesson-a", title: "第一课" }], percent: 50, completed: false, updatedAt: "2026-10-25T00:00:00Z" }], feedback: [{ title: "老师反馈", content: "继续练习", created_at: "2026-10-25" }], notifications: [{ title: "课堂通知", content: "带画笔", created_at: "2026-10-25" }] } }));
  await page.route("**/parent-portal/students/student-a/works", (route) => route.fulfill({ json: { works: [{ workId: "work-a", title: "小海龟", kind: "text" }] } }));
  await page.route("**/parent-portal/students/student-a/works/work-a", (route) => route.fulfill({ json: { workId: "work-a", title: "小海龟", kind: "text", content: "海底故事", coverUrl: "" } }));
  await page.goto("/parent");
  await expect(page.getByRole("heading", { name: "一起看见孩子的成长" })).toBeVisible();
  await expect(page.getByText("海洋创作课")).toBeVisible();
  await expect(page.getByText("继续练习")).toBeVisible();
  await expect(page.getByText("课堂通知")).toBeVisible();
  await page.getByRole("link", { name: /小海龟/ }).click();
  await expect(page.getByText("海底故事")).toBeVisible();
});
