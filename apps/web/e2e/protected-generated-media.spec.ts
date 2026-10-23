import { expect, test } from "@playwright/test";


const image = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==", "base64");
const work = {
  assetId: "protected-art", projectId: "project", ownerUserId: "student", kind: "image",
  title: "魔法森林", previewUrl: "http://localhost:8000/generated-assets/job-art.png",
  prompt: "森林里的魔法书", content: "", reviewState: "approved", featured: false,
  coverUrl: "", processSteps: [], gradeMin: 3, gradeMax: 6, visibility: "organization", isExample: false,
};

test("student previews and downloads a generated file using authorization", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student", organizationId: "school", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  await page.route("**/settings/student-access", route => route.fulfill({ json: { enabled: true, displayName: "星芽", maintenanceMessage: "" } }));
  await page.route("http://127.0.0.1:8000/works/protected-art", route => route.fulfill({ json: work }));
  await page.route("http://127.0.0.1:8000/works/protected-art/comments", route => route.fulfill({ json: { comments: [], likeCount: 0, liked: false, favoriteCount: 0, favorited: false } }));
  let authorizedRequests = 0;
  await page.route("http://127.0.0.1:8000/generated-assets/job-art.png", async route => {
    expect(route.request().headers().authorization).toBe("Bearer student-token");
    authorizedRequests += 1;
    await route.fulfill({ contentType: "image/png", body: image });
  });
  await page.goto("/works/protected-art");
  const preview = page.getByRole("img", { name: "魔法森林作品预览" });
  await expect(preview).toHaveAttribute("src", /^blob:/);
  await expect.poll(() => preview.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载作品" }).click();
  expect((await downloaded).suggestedFilename()).toBe("魔法森林.png");
  expect(authorizedRequests).toBeGreaterThanOrEqual(2);
});

test("public generated work uses its share endpoint without a login token", async ({ page }) => {
  await page.route("**/settings/student-access", route => route.fulfill({ json: { enabled: true, displayName: "星芽", maintenanceMessage: "" } }));
  await page.route("http://127.0.0.1:8000/shares/public/public-art", route => route.fulfill({ json: { work: { ...work, previewUrl: "/shares/public/public-art/media/preview" }, allowDownload: false } }));
  await page.route("http://127.0.0.1:8000/shares/public/public-art/media/preview", async route => {
    expect(route.request().headers().authorization).toBeUndefined();
    await route.fulfill({ contentType: "image/png", body: image });
  });
  await page.goto("/share/public-art");
  const preview = page.getByRole("img", { name: "魔法森林作品预览" });
  await expect(preview).toHaveAttribute("src", "http://127.0.0.1:8000/shares/public/public-art/media/preview");
  await expect.poll(() => preview.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
});

test("personal work and asset galleries render protected thumbnails", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("ai-workbench-session", JSON.stringify({ userId: "student", organizationId: "school", role: "student", accessToken: "student-token", expiresAt: "2099-01-01T00:00:00.000Z" })));
  await page.route("**/settings/student-access", route => route.fulfill({ json: { enabled: true, displayName: "星芽", maintenanceMessage: "" } }));
  await page.route("http://127.0.0.1:8000/works/mine", route => route.fulfill({ json: { works: [work] } }));
  await page.route("http://127.0.0.1:8000/generated-assets/job-art.png", async route => {
    expect(route.request().headers().authorization).toBe("Bearer student-token");
    await route.fulfill({ contentType: "image/png", body: image });
  });
  for (const path of ["/projects", "/assets"]) {
    await page.goto(path);
    const preview = page.getByRole("img", { name: /魔法森林/ });
    await expect(preview).toHaveAttribute("src", /^blob:/);
    await expect.poll(() => preview.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  }
});
