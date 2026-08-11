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

test("shows the invalid-invitation notice for a bogus token", async ({ page }) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过实时邀请预览")

  await page.goto("/invite/bogus-token")

  await expect(page.getByRole("heading", { name: "邀请无效" })).toBeVisible()
  await expect(page.getByText(/邀请链接无效/)).toBeVisible()
})

test("requires login for the security settings page", async ({ page }) => {
  await page.goto("/settings/security")

  await expect(page.getByRole("heading", { name: "安全设置" })).toBeVisible()
  await expect(page.getByText("请先")).toBeVisible()
  await expect(page.getByRole("link", { name: "登录" }).first()).toBeVisible()
})

test("requires login for the members page", async ({ page }) => {
  await page.goto("/members")

  await expect(page.getByRole("heading", { name: "成员管理" })).toBeVisible()
  await expect(page.getByRole("link", { name: "登录" }).first()).toBeVisible()
})

test("requires login for the usage page", async ({ page }) => {
  await page.goto("/usage")

  await expect(page.getByRole("heading", { name: "用量与套餐" })).toBeVisible()
  await expect(page.getByRole("link", { name: "登录" }).first()).toBeVisible()
})

test("requires login for the jobs page", async ({ page }) => {
  await page.goto("/jobs")

  await expect(page.getByRole("heading", { name: "职位管理" })).toBeVisible()
  await expect(page.getByRole("link", { name: "登录" }).first()).toBeVisible()
})

test("renders the members page for a freshly registered owner", async ({ page }) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过实时成员页流程")

  const email = `e2e-${Date.now()}@example.com`

  await page.goto("/register")
  await page.getByLabel("邮箱").fill(email)
  await page.getByLabel("密码").fill("e2e-password-1")
  await page.getByLabel("显示名称").fill("E2E 用户")
  await page.getByRole("button", { name: "创建账户" }).click()
  await page.waitForURL("/")

  await page.goto("/members")

  await expect(page.getByRole("heading", { name: "成员列表" })).toBeVisible()
  await expect(page.getByRole("cell", { name: email })).toBeVisible()
  await expect(page.getByRole("cell", { name: "所有者" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "邀请成员" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "邀请记录" })).toBeVisible()
})

test("renders the security page with the MFA setup call-to-action", async ({ page }) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过实时安全设置流程")

  const email = `e2e-${Date.now()}@example.com`

  await page.goto("/register")
  await page.getByLabel("邮箱").fill(email)
  await page.getByLabel("密码").fill("e2e-password-1")
  await page.getByLabel("显示名称").fill("E2E 安全用户")
  await page.getByRole("button", { name: "创建账户" }).click()
  await page.waitForURL("/")

  await page.goto("/settings/security")

  await expect(page.getByRole("heading", { name: "两步验证（MFA）" })).toBeVisible()
  await expect(page.getByRole("button", { name: "设置两步验证" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "租户 MFA 策略" })).toBeVisible()
})

test("creates, activates, and uploads a material for a job", async ({ page }, testInfo) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过实时职位流程")

  const stamp = Date.now()
  const email = `e2e-${stamp}@example.com`
  const companyName = `E2E 企业 ${stamp}`

  await page.goto("/register")
  await page.getByLabel("邮箱").fill(email)
  await page.getByLabel("密码").fill("e2e-password-1")
  await page.getByLabel("显示名称").fill("E2E 职位用户")
  await page.getByRole("button", { name: "创建账户" }).click()
  await page.waitForURL("/")

  await page.goto("/companies")
  await page.getByLabel("企业名称").fill(companyName)
  await page.getByRole("button", { name: "创建企业" }).click()
  await page.waitForURL(/\/companies\/[0-9a-f-]+$/)

  await page.goto("/jobs")
  await expect(page.getByRole("link", { name: "职位" }).first()).toBeVisible()
  await page.getByText("请选择企业").click()
  await page.getByRole("option", { name: companyName }).click()
  await page.getByLabel("职位名称").fill("高级后端工程师")
  await page.getByRole("button", { name: "创建职位" }).click()
  await page.waitForURL(/\/jobs\/[0-9a-f-]+$/)

  await expect(page.getByRole("heading", { name: "高级后端工程师" })).toBeVisible()
  await expect(page.getByText("草稿", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "编辑职位" })).toBeVisible()

  await page.setInputFiles("#file", {
    name: "jd.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("e2e job description body"),
  })
  const uploadButton = page.getByRole("button", { name: "上传材料", exact: true })
  await uploadButton.click()
  await page.waitForLoadState("networkidle")
  await page.reload()
  await page.waitForLoadState("networkidle")
  await expect(
    page.getByRole("region", { name: "职位材料" }).getByRole("cell", { name: "jd.txt" }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "下载" }).first()).toBeVisible()

  await page.getByRole("button", { name: "启用职位" }).click()
  await page.waitForLoadState("networkidle")
  await page.reload()
  await page.waitForLoadState("networkidle")
  await expect(page.getByText("活跃", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "编辑职位" })).toHaveCount(0)
  await expect(page.getByRole("link", { name: "下载" }).first()).toBeVisible()

  await page.goto("/jobs")
  await expect(page.getByRole("link", { name: "高级后端工程师" })).toBeVisible()

  await testInfo.attach("jobs-detail", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})
