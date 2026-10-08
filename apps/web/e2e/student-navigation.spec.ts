import { expect, test } from "@playwright/test";

test("student can use the creative home entrances and reach the course space", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "✦ 星芽 AI 创作岛" })).toBeVisible();
  await expect(page.getByRole("link", { name: "登录" })).toHaveAttribute("href", "/login");
  await expect(page.getByAltText("打开的 AI 创作书与知识河")).toBeVisible();
  const entrances = [
    [/AI 对话/, "/workspace/chat"],
    [/网页创作/, "/workspace/html"],
    [/图片创作/, "/workspace/image"],
    [/音乐创作/, "/workspace/music"],
    [/视频创作/, "/workspace/video"],
    [/智能体中心/, "/agents"],
  ] as const;
  for (const [name, href] of entrances) await expect(page.getByRole("link", { name })).toHaveAttribute("href", href);
  await page.locator('a[href="/courses"]').click();
  await expect(page).toHaveURL(/\/courses/);
  await expect(page.getByRole("heading", { name: "我的课程" })).toBeVisible();
});

test("every creation mode opens an actionable task panel", async ({ page }) => {
  const workspaces = [
    ["/workspace/chat", "AI 对话任务设置"],
    ["/workspace/image", "AI 绘画任务设置"],
    ["/workspace/music", "AI 音乐任务设置"],
    ["/workspace/video", "AI 视频任务设置"],
  ] as const;
  for (const [path, panel] of workspaces) {
    await page.goto(path);
    await expect(page.getByRole("region", { name: panel })).toBeVisible();
    await expect(page.getByRole("button", { name: "立即生成" })).toBeVisible();
  }
});

test("student workspaces expose prompt polishing controls", async ({ page }) => {
  await page.goto("/workspace/image");
  await expect(page.getByRole("button", { name: "✨ 帮我润色" }).first()).toBeVisible();

  await page.goto("/workspace/html");
  await expect(page.getByRole("button", { name: "✨ 帮我润色" })).toBeVisible();
});

test("student can enter the image creation workspace", async ({ page }) => {
  await page.goto("/workspace/image");
  await expect(page.getByRole("region", { name: "AI 绘画任务设置" })).toBeVisible();
});

test("creation workspaces receive a prompt from a course or inspiration link", async ({ page }) => {
  await page.goto("/workspace/image?prompt=%E7%94%BB%E4%B8%80%E5%8F%AA%E6%9C%88%E7%90%83%E5%B0%8F%E5%85%94");
  await expect(page.getByLabel("创意描述")).toHaveValue("画一只月球小兔");

  await page.goto("/workspace/html?prompt=%E5%81%9A%E4%B8%80%E4%B8%AA%E6%A0%A1%E5%9B%AD%E6%A4%8D%E7%89%A9%E7%BD%91%E9%A1%B5");
  await expect(page.getByPlaceholder("例如：把标题改成海底探险，颜色更明亮")).toHaveValue("做一个校园植物网页");
});

test("video workspace requires a reference image only for image-to-video", async ({ page }) => {
  await page.goto("/workspace/video");
  await page.getByLabel("创意描述").fill("小机器人在教室里发现星星门");
  await expect(page.getByRole("button", { name: "立即生成" })).toBeDisabled();
  await page.getByRole("button", { name: "文生视频" }).click();
  await expect(page.getByRole("button", { name: "立即生成" })).toBeEnabled();
});

test("default HTML example has an interactive preview button", async ({ page }) => {
  await page.goto("/workspace/html");
  const preview = page.frameLocator('iframe[title="网页预览"]');
  await preview.getByRole("button", { name: "开始探索" }).click();
  await expect(preview.getByText("发现一颗会发光的蓝色星球！")).toBeVisible();
});

test("student can browse and run local HTML game examples", async ({ page }) => {
  await page.goto("/play");
  await expect(page.getByRole("heading", { name: "小游戏试玩乐园" })).toBeVisible();
  await page.locator('a[href="/play/snake"]').click();
  await expect(page).toHaveURL(/\/play\/snake/);
  await expect(page.getByTitle("贪吃蛇小游戏试玩")).toBeVisible();
});

test("student content pages always render a useful workspace or empty state", async ({ page }) => {
  const pages = [
    ["/inspiration", "不知道做什么？从一个案例开始"],
    ["/projects", "我的作品"],
    ["/assets", "我的素材"],
    ["/courses", "我的课程"],
    ["/showcase", "同学作品展示墙"],
    ["/student/reports", "我的成长报告"],
    ["/agents", "智能体中心"],
  ] as const;

  for (const [path, heading] of pages) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
});

test("teacher feature pages render their working surfaces", async ({ page }) => {
  const pages = [
    ["/teacher", "今天的课堂"],
    ["/teacher/classes", "班级管理"],
    ["/teacher/classroom", "还没有可监看的课堂"],
    ["/teacher/courses", "课程编辑器"],
    ["/teacher/flows", "教学流程"],
    ["/teacher/review", "作品审核"],
    ["/teacher/reports", "学习报告"],
    ["/teacher/knowledge", "知识库"],
    ["/teacher/exports", "课程导出"],
  ] as const;

  for (const [path, heading] of pages) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
});

test("administrator can open the operations dashboard and provider configuration", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({
      userId: "admin-e2e",
      organizationId: "org-e2e",
      role: "platform_admin",
      accessToken: "e2e-token",
      expiresAt: "2099-01-01T00:00:00.000Z",
    }));
  });
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "平台运营总览" })).toBeVisible();
  await page.getByRole("link", { name: "配置 AI 能力" }).first().click();
  await expect(page).toHaveURL(/\/admin\/providers/);
});

test("teacher can open the course editor", async ({ page }) => {
  await page.goto("/teacher/courses");
  await expect(page.getByRole("heading", { name: "课程编辑器" })).toBeVisible();
  await expect(page.getByRole("button", { name: "＋ 选择文件" })).toBeVisible();
});
