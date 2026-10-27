import { expect, test } from "@playwright/test";

const adminSession = { userId: "admin-e2e", organizationId: "org-e2e", role: "platform_admin", accessToken: "admin-token", expiresAt: "2099-01-01T00:00:00.000Z" };

test("ordinary login stays for students, teachers and parents", async ({ page }) => {
  await page.goto("/login?next=%2Fadmin%2Fusers");
  await expect(page.getByRole("heading", { name: "欢迎回来！" })).toBeVisible();
  await expect(page.getByText("管理员登录")).toHaveCount(0);
  await page.route("**/auth/login", (route) => route.fulfill({ status: 401, json: { detail: "invalid credentials" } }));
  await page.getByLabel("我的平台账号").fill("operator");
  await page.getByLabel("登录密码").fill("incorrect-password");
  await page.getByRole("button", { name: /进入我的创作岛/ }).click();
  await expect(page.locator(".auth-card__message")).toContainText("账号或密码不正确");
});

test("administrator uses the separate sign-in page", async ({ page }) => {
  await page.route("**/auth/admin/login", (route) => route.fulfill({ json: adminSession }));
  await page.goto("/admin/sign-in?next=%2Fadmin%2Fusers");
  await expect(page.getByRole("heading", { name: "管理员登录" })).toBeVisible();
  await page.getByLabel("管理员账号").fill("operator");
  await page.getByLabel("登录密码").fill("admin-password");
  await page.getByRole("button", { name: /进入管理后台/ }).click();
  await expect(page).toHaveURL(/\/admin\/users$/);
  await expect(page.getByRole("heading", { name: "账号管理" })).toBeVisible();
});
