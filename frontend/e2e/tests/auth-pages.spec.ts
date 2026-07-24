import { expect, test } from "@playwright/test"

const apiBaseUrl = process.env["API_INTERNAL_URL"] ?? "http://localhost:8000"

async function isAuthApiAvailable(): Promise<boolean> {
  try {
    // A deployed auth API answers 401 here; an older API build answers 404.
    const response = await fetch(new URL("/auth/me", apiBaseUrl))
    return response.status === 401
  } catch {
    return false
  }
}

test("renders the register page", async ({ page }) => {
  await page.goto("/register")

  await expect(page.getByRole("heading", { name: "注册" })).toBeVisible()
  await expect(page.getByLabel("邮箱")).toBeVisible()
  await expect(page.getByLabel("密码")).toBeVisible()
  await expect(page.getByLabel("显示名称")).toBeVisible()
  await expect(page.getByLabel("租户名称")).toBeVisible()
  await expect(page.getByText("选填，留空则自动生成")).toBeVisible()
  await expect(page.getByRole("button", { name: "创建账户" })).toBeVisible()
  await expect(page.getByRole("link", { name: "直接登录" })).toBeVisible()
})

test("renders the login page", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByRole("heading", { name: "登录" })).toBeVisible()
  await expect(page.getByLabel("邮箱")).toBeVisible()
  await expect(page.getByLabel("密码")).toBeVisible()
  await expect(page.getByRole("button", { name: "登录" })).toBeVisible()
  await expect(page.getByRole("link", { name: "立即注册" })).toBeVisible()
})

test("shows validation feedback without a backend", async ({ page }) => {
  await page.goto("/register")

  await page.getByRole("button", { name: "创建账户" }).click()

  await expect(page.getByText("邮箱格式不正确")).toBeVisible()
  await expect(page.getByText("密码至少 8 位")).toBeVisible()
  await expect(page.getByText("显示名称必填")).toBeVisible()
})

test("completes a register, logout and login round trip", async ({ page }) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过实时账户流程")

  const email = `e2e-${Date.now()}@example.com`
  const password = "e2e-password-1"

  await page.goto("/register")
  await page.getByLabel("邮箱").fill(email)
  await page.getByLabel("密码").fill(password)
  await page.getByLabel("显示名称").fill("E2E 测试用户")
  await page.getByRole("button", { name: "创建账户" }).click()

  await page.waitForURL("/")
  await expect(page.getByText("E2E 测试用户", { exact: true })).toBeVisible()
  await expect(page.getByText("角色：租户所有者")).toBeVisible()

  await page.getByRole("button", { name: "退出登录" }).click()
  await page.waitForURL("/")
  await expect(page.getByRole("link", { name: "登录" })).toBeVisible()

  await page.goto("/login")
  await page.getByLabel("邮箱").fill(email)
  await page.getByLabel("密码").fill(password)
  await page.getByRole("button", { name: "登录" }).click()

  await page.waitForURL("/")
  await expect(page.getByText("E2E 测试用户", { exact: true })).toBeVisible()
})
