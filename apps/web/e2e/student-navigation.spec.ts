import { expect, test } from "@playwright/test";
import { mockAgentWorkspace } from "./agent-fixture";
async function loginAsStudent(page: import("@playwright/test").Page) {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  await page.route("**/settings/student-access", (route) => route.fulfill({ json: { enabled: true, displayName: "星芽", maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all", videoDurationSeconds: 5 } }));
}


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
  await loginAsStudent(page);
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

test("creation workspaces expose floating page navigation controls", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/chat");
  await expect(page.getByRole("navigation", { name: "工作台页面导航" })).toBeVisible();
  await expect(page.getByRole("button", { name: "向上查看输入区" })).toBeVisible();
  await expect(page.getByRole("button", { name: "向下查看生成结果" })).toBeVisible();
});

test("creation form keeps the generate action inside the first viewport", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/chat");
  const form = page.getByRole("region", { name: "AI 对话任务设置" });
  const generateButton = page.getByRole("button", { name: "立即生成" });
  const formBox = await form.boundingBox();
  const buttonBox = await generateButton.boundingBox();
  expect(formBox).not.toBeNull();
  expect(buttonBox).not.toBeNull();
  expect(buttonBox!.y + buttonBox!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  expect(buttonBox!.y).toBeGreaterThan(formBox!.y);
});

test("student workspaces expose prompt polishing controls", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/image");
  await expect(page.getByRole("button", { name: "✨ 帮我润色" }).first()).toBeVisible();

  await page.goto("/workspace/html");
  await expect(page.getByRole("button", { name: "✨ 帮我润色" })).toBeVisible();
});

test("image workspace shows visual style examples and expanded ratios", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/image");
  await expect(page.getByLabel("创意描述")).toBeVisible();
  await expect(page.getByRole("button", { name: /Q版卡通/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /3D盲盒/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "3:4" })).toBeVisible();
  await expect(page.getByRole("button", { name: "4:3" })).toBeVisible();
});

test("HTML workspace offers examples and returns to the previous creation page", async ({ page }) => {
  await page.goto("/workspace/image");
  await page.goto("/workspace/html");
  await page.getByRole("button", { name: /魔法书首页/ }).click();
  await expect(page.getByPlaceholder("例如：把标题改成海底探险，颜色更明亮")).toHaveValue(/魔法书首页/);
  await page.getByRole("button", { name: "← 返回上一页" }).click();
  await expect(page).toHaveURL(/\/workspace\/image/);
});

test("HTML workspace keeps the input visible and can open its preview on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 680, height: 800 });
  await page.goto("/workspace/html");
  const prompt = page.getByLabel("描述你想做的网页");
  await expect(prompt).toBeInViewport();
  await page.getByRole("button", { name: "打开网页预览" }).click();
  await expect(page.getByRole("dialog", { name: "网页全屏预览" })).toBeVisible();
  await expect(page.getByTitle("网页全屏预览")).toBeInViewport();
  await page.getByRole("button", { name: "关闭预览" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("HTML workspace reopens the student's last generated page", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-html", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  await page.route("**/settings/student-access", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled: true, displayName: "星芽 AI 创作岛", maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "popular", showcaseKind: "all" }) }));
  let saved = false;
  const generated = { projectId: "web-student-html", assetId: "asset-html", currentVersion: { versionId: "web-student-html-v1", title: "魔法书", html: "<!doctype html><html><body><h1>我的魔法书</h1></body></html>", teachingSteps: ["先定主题", "再看预览"] } };
  await page.route("**/projects/web-student-html/html", async (route) => route.fulfill(saved ? { contentType: "application/json", body: JSON.stringify(generated) } : { status: 404 }));
  await page.route("**/projects/web-student-html/html/generate", async (route) => { saved = true; await route.fulfill({ contentType: "application/json", body: JSON.stringify(generated) }); });
  await page.goto("/workspace/html");
  await page.getByLabel("描述你想做的网页").fill("做一本魔法书");
  await page.getByRole("button", { name: "发送并生成" }).click();
  await expect(page.frameLocator('iframe[title="网页预览"]').getByRole("heading", { name: "我的魔法书" })).toBeVisible();
  await page.reload();
  await expect(page.frameLocator('iframe[title="网页预览"]').getByRole("heading", { name: "我的魔法书" })).toBeVisible();
  await expect(page.getByText("已找回你上次创作的网页")).toBeVisible();
});

test("HTML workspace directs students to login instead of silently failing", async ({ page }) => {
  await page.goto("/workspace/html");
  await page.getByLabel("描述你想做的网页").fill("做一个森林网页");
  await page.getByRole("button", { name: "发送并生成" }).click();
  await expect(page.getByRole("link", { name: "去登录 →" })).toHaveAttribute("href", "/login?next=%2Fworkspace%2Fhtml");
});

test("student can enter the image creation workspace", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/image");
  await expect(page.getByRole("region", { name: "AI 绘画任务设置" })).toBeVisible();
});

test("home example works open a work detail instead of redirecting into a creation form", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /会发光的魔法书/ }).click();
  await expect(page).toHaveURL(/\/works\/examples\/magic-book/);
  await expect(page.getByRole("heading", { name: "会发光的魔法书" })).toBeVisible();
  await expect(page.getByRole("link", { name: "用这个灵感开始创作" })).toHaveAttribute("href", /\/workspace\/html\?prompt=/);
});

test("student builds an agent, selects a model, and receives its test response", async ({ page }) => {
  const fixture = await mockAgentWorkspace(page);
  await page.goto("/agents");
  await page.getByLabel("选择大模型").selectOption("deepseek-class");
  await page.getByLabel("指令 *").fill("你是月球故事向导，先讲一段故事，再提出建议。");
  await page.getByLabel("测试问题").fill("写一个月球花园故事");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(page.getByText("月球花园里，小兔子勇敢地种下第一朵彩虹花。")).toBeVisible();
  expect(fixture.getProfile()?.instructions).toContain("你是月球故事向导");
  await page.reload();
  await expect(page.getByText("月球花园里，小兔子勇敢地种下第一朵彩虹花。")).toBeVisible();
  await expect(page.getByRole("link", { name: "查看作品", exact: true })).toHaveAttribute("href", "/works/agent-work");
});

test("public share displays saved text and resolves uploaded media", async ({ page }) => {
  const shared = { assetId: "work-1", projectId: "p-1", ownerUserId: "student-1", kind: "image", title: "森林城堡", previewUrl: "/works/work-1/media/preview", prompt: "画一座森林城堡", content: "这是一座会发光的森林城堡。", reviewState: "approved", featured: false, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false };
  await page.route("**/shares/public/demo", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ work: shared, allowDownload: false }) }));
  await page.goto("/share/demo");
  await expect(page.getByRole("img", { name: "森林城堡作品预览" })).toHaveAttribute("src", /127\.0\.0\.1:8000\/shares\/public\/demo\/media\/preview/);
  await expect(page.getByText("这是一座会发光的森林城堡。")).toBeVisible();
});

test("signed-in student can preview a protected uploaded image", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  await page.route("**/settings/student-access", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled: true, displayName: "星芽", maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "popular", showcaseKind: "all" }) }));
  const work = { assetId: "work-1", projectId: "p-1", ownerUserId: "student-e2e", kind: "image", title: "森林城堡", previewUrl: "/works/work-1/media/preview", prompt: "森林", content: "", reviewState: "approved", featured: false, coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false };
  await page.route("http://127.0.0.1:8000/works/work-1", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(work) }));
  await page.route("http://127.0.0.1:8000/works/work-1/comments", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ comments: [], likeCount: 0, liked: false, favoriteCount: 0, favorited: false }) }));
  let authorized = false;
  await page.route("http://127.0.0.1:8000/works/work-1/media/preview", async (route) => {
    authorized = route.request().headers().authorization === "Bearer student-token";
    await route.fulfill({ contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==", "base64") });
  });
  await page.goto("/works/work-1");
  await expect(page.getByRole("img", { name: "森林城堡作品预览" })).toHaveAttribute("src", /^blob:/);
  expect(authorized).toBe(true);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载作品" }).click();
  expect((await download).suggestedFilename()).toBe("森林城堡.png");
});

test("student saves agent instructions and reopens them after reload", async ({ page }) => {
  await mockAgentWorkspace(page);
  await page.goto("/agents");
  await page.getByLabel("名称 *").fill("月球故事向导");
  await page.getByLabel("指令 *").fill("先写一段月球故事，再问我下一步要做什么。");
  await page.getByRole("button", { name: "保存设置" }).click();
  await expect(page.getByText("智能体设置已保存，下次登录还可以继续使用。")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("指令 *")).toHaveValue("先写一段月球故事，再问我下一步要做什么。");
});

test("creation workspaces receive a prompt from a course or inspiration link", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/image?prompt=%E7%94%BB%E4%B8%80%E5%8F%AA%E6%9C%88%E7%90%83%E5%B0%8F%E5%85%94");
  await expect(page.getByLabel("创意描述")).toHaveValue("画一只月球小兔");

  await page.goto("/workspace/html?prompt=%E5%81%9A%E4%B8%80%E4%B8%AA%E6%A0%A1%E5%9B%AD%E6%A4%8D%E7%89%A9%E7%BD%91%E9%A1%B5");
  await expect(page.getByPlaceholder("例如：把标题改成海底探险，颜色更明亮")).toHaveValue("做一个校园植物网页");
});

test("video workspace requires a reference image only for image-to-video", async ({ page }) => {
  await loginAsStudent(page);
  await page.goto("/workspace/video");
  await page.getByLabel("创意描述").fill("小机器人在教室里发现星星门");
  await expect(page.getByRole("button", { name: "立即生成" })).toBeDisabled();
  await page.getByRole("button", { name: "文生视频" }).click();
  await expect(page.getByRole("button", { name: "立即生成" })).toBeEnabled();
});

test("image workspace resumes the pending job after a reload", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student-e2e", organizationId: "org-e2e", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" }));
  });
  await page.route("**/settings/student-access", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled: true, displayName: "星芽", maintenanceMessage: "", showcaseColumns: 4, showcaseRows: 2, showcaseSort: "featured", showcaseKind: "all", videoDurationSeconds: 5 }) }));
  await page.route("**/media/jobs/job-e2e", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ jobId: "job-e2e", kind: "image", state: "succeeded", assetId: "asset-e2e", progress: 100 }) }));
  await page.route("**/works/asset-e2e", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ assetId: "asset-e2e", kind: "image", title: "小海龟", previewUrl: "data:image/png;base64,iVBORw0KGgo=", lyrics: "" }) }));

  await page.goto("/workspace/image");
  await page.evaluate(() => window.sessionStorage.setItem("ai-workbench-active-job:org-e2e:student-e2e:image", "job-e2e"));
  await page.reload();
  await expect(page.getByText("创作完成")).toBeVisible();
  await expect(page.getByAltText("小海龟")).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.sessionStorage.getItem("ai-workbench-active-job:org-e2e:student-e2e:image"))).toBeNull();
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
    ["/agents", "创建我的智能体"],
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
