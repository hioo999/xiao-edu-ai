import { expect, test } from "@playwright/test";

async function loginAsAdmin(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({
      userId: "admin-e2e",
      organizationId: "org-e2e",
      role: "platform_admin",
      accessToken: "e2e-token",
      expiresAt: "2099-01-01T00:00:00.000Z",
    }));
  });
}

async function loginAsTeacher(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "teacher-e2e", organizationId: "org-e2e", role: "teacher", accessToken: "teacher-token", expiresAt: "2099-01-01T00:00:00.000Z" }));
  });
}

test("administrator reaches account, moderation, and operations sections", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "账号管理" })).toBeVisible();
  await expect(page.getByRole("button", { name: "批量启用" })).toBeVisible();

  await page.goto("/admin/moderation");
  await expect(page.getByRole("heading", { name: "安全审核" })).toBeVisible();
  await expect(page.getByRole("button", { name: "保存策略" })).toBeVisible();

  await page.goto("/admin/operations");
  await expect(page.getByRole("heading", { name: "系统运维" })).toBeVisible();
  await expect(page.getByRole("button", { name: "刷新状态" })).toBeVisible();
});

test("administrator can edit a Skill teaching rule before saving", async ({ page }) => {
  await loginAsAdmin(page);
  await page.route("**/agents/skills", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ skills: [{ tool_id: "story-outline", kind: "skill", name: "故事创作步骤", capabilities: "text", enabled: true, instruction: "先鼓励学生说出主角。" }] }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ tool_id: "story-outline", kind: "skill", name: "故事创作步骤", capabilities: "text", enabled: true, instruction: "先选角色，再给出三步提示。" }) });
  });

  await page.goto("/admin/skills");
  await expect(page.getByText("故事创作步骤")).toBeVisible();
  await page.getByRole("button", { name: "编辑" }).click();
  await expect(page.getByLabel("教学规则")).toHaveValue("先鼓励学生说出主角。");
  await page.getByLabel("教学规则").fill("先选角色，再给出三步提示。");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByText("配置已更新。")).toBeVisible();
});

test("teacher workbench sections render their real tools", async ({ page }) => {
  const sections = [
    { path: "/teacher/classes", heading: "班级管理" },
    { path: "/teacher/flows", heading: "教学流程" },
    { path: "/teacher/review", heading: "作品审核" },
    { path: "/teacher/reports", heading: "学习报告" },
    { path: "/teacher/knowledge", heading: "知识库" },
    { path: "/teacher/exports", heading: "课程导出" },
  ];

  for (const section of sections) {
    await page.goto(section.path);
    await expect(page.getByRole("heading", { name: section.heading })).toBeVisible();
  }
});

test("student growth report page renders with a helpful empty state", async ({ page }) => {
  await page.goto("/student/reports");
  await expect(page.getByRole("heading", { name: "我的成长报告" })).toBeVisible();
  await expect(page.getByText("登录后即可查看自己的成长报告。")).toBeVisible();
});

test("student can generate text and save it into the review workflow", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" }));
  });
  await page.route("**/settings/student-access", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled: true, displayName: "星芽", maintenanceMessage: "" }) });
  });
  let savedWork: Record<string, unknown> | null = null;
  await page.route("**/models/text/generate", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ content: "小海龟决定带大家清理海底花园。", providerId: "mock-text", modelId: "mock-model" }) });
  });
  await page.route("**/works", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const requestWork = route.request().postDataJSON() as Record<string, unknown>;
    savedWork = requestWork;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ assetId: "asset-e2e", projectId: "text-student-e2e", ownerUserId: "student-e2e", kind: "text", title: "AI 对话：海底花园", previewUrl: "", prompt: requestWork.prompt, reviewState: "pending", featured: false, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false }) });
  });

  await page.goto("/workspace/chat");
  await page.getByLabel("创意描述").fill("帮我写一个海底花园的故事开头");
  await page.getByRole("button", { name: "立即生成" }).click();

  await expect(page.getByText("小海龟决定带大家清理海底花园。")).toBeVisible();
  await expect(page.getByText("创作完成")).toBeVisible();
  expect(savedWork).toMatchObject({ kind: "text", projectId: "text-student-e2e", prompt: "帮我写一个海底花园的故事开头" });
});

test("administrator can edit showcase metadata and upload inputs are available", async ({ page }) => {
  await loginAsAdmin(page);
  const work = { assetId: "asset-showcase", projectId: "p-1", ownerUserId: "student-e2e", kind: "video", title: "魔法书", previewUrl: "/samples/magic-book.mp4", prompt: "翻开魔法书", reviewState: "pending", featured: false, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false };
  await page.route("**/works/review?*", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ works: [work] }) }));
  await page.route("**/settings", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ displayName: "星芽", studentHomeEnabled: true, maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all" }) }));
  await page.route("**/works/asset-showcase/metadata", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ...work, title: "魔法书翻开", isExample: true, processSteps: ["选择主题"] }) }));

  await page.goto("/admin/showcase");
  await page.getByRole("button", { name: "编辑资料" }).click();
  await expect(page.getByLabel("上传封面图")).toBeVisible();
  await expect(page.getByLabel("上传预览文件")).toBeVisible();
  await page.getByLabel("作品名称").fill("魔法书翻开");
  await page.getByLabel("创作步骤（每行一步）").fill("选择主题");
  await page.getByLabel("这是教师示例作品").check();
  await page.getByRole("button", { name: "保存作品资料" }).click();
  await expect(page.getByText("作品资料已保存，学生端会立即按新信息展示。")).toBeVisible();
});

test("administrator can register a safe HTTPS preview for an imported web project", async ({ page }) => {
  await loginAsAdmin(page);
  const work = { assetId: "asset-web", projectId: "project-web", ownerUserId: "teacher-e2e", kind: "webpage", title: "森林城堡网站", previewUrl: "", prompt: "森林城堡", reviewState: "approved", featured: true, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: true };
  const deployment = { deploymentId: "deploy-web", assetId: "asset-web", projectType: "node", state: "prepared", manifest: { dependencies: ["next"], hasDatabaseHint: true }, envTemplate: { PORT: "8080" }, createdAt: "2026-10-01T00:00:00.000Z", updatedAt: "2026-10-01T00:00:00.000Z", publishedUrl: "" };
  let publishPayload: Record<string, unknown> | null = null;
  await page.route("**/works/review?*", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ works: [work] }) }));
  await page.route("**/works/asset-web/deployments", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ deployments: [deployment] }) }));
  await page.route("**/works/asset-web/deployments/deploy-web/publish", async (route) => {
    publishPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ deployment: { ...deployment, state: "published", publishedUrl: "https://projects.example.edu/forest-castle" }, work: { ...work, previewUrl: "https://projects.example.edu/forest-castle" } }) });
  });

  await page.goto("/admin/assets");
  await page.getByLabel("deploy-web HTTPS 预览地址").fill("https://projects.example.edu/forest-castle");
  await page.getByRole("button", { name: "登记发布" }).click();

  await expect(page.getByText("部署地址已登记，作品详情可安全预览该网站。")).toBeVisible();
  expect(publishPayload).toEqual({ previewUrl: "https://projects.example.edu/forest-castle" });
  await expect(page.getByRole("button", { name: "更新地址" })).toBeVisible();
});

test("teacher can approve a selected work for the student showcase", async ({ page }) => {
  await loginAsTeacher(page);
  const work = { assetId: "asset-review", projectId: "p-1", ownerUserId: "student-e2e", kind: "image", title: "月球小兔", previewUrl: "", prompt: "小兔在月球花园", reviewState: "pending", featured: false, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false };
  let reviewPayload: Record<string, unknown> | null = null;
  await page.route("**/works/review?*", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ works: [work] }) }));
  await page.route("**/works/review/batch", async (route) => {
    reviewPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ reviewed: 1, works: [{ ...work, reviewState: "approved", featured: true }] }) });
  });

  await page.goto("/teacher/review");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "通过并精选" }).click();

  await expect(page.getByText("已处理 1 个作品。")).toBeVisible();
  expect(reviewPayload).toEqual({ assetIds: ["asset-review"], state: "approved", featured: true });
});

test("student sees an approved work on the showcase page", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" }));
  });
  await page.route("**/settings/student-access", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled: true, displayName: "星芽", maintenanceMessage: "" }) });
  });
  const work = { assetId: "asset-review", projectId: "p-1", ownerUserId: "student-other", kind: "image", title: "月球小兔", previewUrl: "", prompt: "小兔在月球花园", reviewState: "approved", featured: true, coverUrl: "", processSteps: ["选主题"], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false, likeCount: 2, favoriteCount: 1, liked: false, favorited: false };
  await page.route("**/works/showcase?*", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ works: [work] }) }));
  await page.route("**/works/asset-review/comments", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ comments: [], likeCount: 2, liked: false }) }));

  await page.goto("/showcase");
  await expect(page.getByRole("heading", { name: "同学作品展示墙" })).toBeVisible();
  await expect(page.getByRole("region", { name: "筛选作品" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "老师精选" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "月球小兔" })).toBeVisible();
  await expect(page.getByRole("link", { name: "老师精选：月球小兔" })).toHaveAttribute("href", "/works/asset-review");
});

test("student can filter and search the showcase without distorted cards", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" }));
  });
  const works = [
    { assetId: "asset-web", projectId: "p-1", ownerUserId: "student-a", kind: "webpage", title: "魔法书网页", previewUrl: "", prompt: "会翻页的魔法书", reviewState: "approved", featured: false, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 4, visibility: "organization", isExample: false, likeCount: 9, favoriteCount: 3, liked: false, favorited: false },
    { assetId: "asset-video", projectId: "p-2", ownerUserId: "student-b", kind: "video", title: "星星列车", previewUrl: "", prompt: "列车穿过云海", reviewState: "approved", featured: false, coverUrl: "", processSteps: [], gradeMin: 5, gradeMax: 6, visibility: "organization", isExample: false, likeCount: 8, favoriteCount: 2, liked: false, favorited: false },
  ];
  await page.route("**/settings/student-access", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled: true, displayName: "星芽", maintenanceMessage: "" }) });
  });
  await page.route("**/works/showcase?*", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ works }) }));
  await page.goto("/showcase");

  await page.getByRole("button", { name: "网页", exact: true }).click();
  await expect(page.getByRole("heading", { name: "魔法书网页" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "星星列车" })).toBeHidden();
  await page.getByPlaceholder("搜索作品名称或创意").fill("不存在的作品");
  await expect(page.getByRole("heading", { name: "没有找到符合条件的作品" })).toBeVisible();
});
