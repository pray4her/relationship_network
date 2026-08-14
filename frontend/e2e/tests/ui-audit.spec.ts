import { createHmac } from "node:crypto"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import type { Page } from "@playwright/test"
import { expect, test } from "@playwright/test"

test.skip(process.env["UI_AUDIT"] !== "1", "仅按需执行的 UI 审计截图工具")

const shotsDir = path.resolve(process.cwd(), process.env["UI_AUDIT_SHOTS"] ?? "../../shots/audit")
const adminStatePath = path.resolve(process.cwd(), "../../shots/.ui-audit-admin.json")
const adminEmail = "ui-audit-admin@example.com"
const password = "ui-audit-password-1"

function decodeBase32(value: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
  let bits = ""
  for (const character of value.replaceAll("=", "").toUpperCase()) {
    const index = alphabet.indexOf(character)
    if (index < 0) throw new Error("invalid base32 secret")
    bits += index.toString(2).padStart(5, "0")
  }
  const bytes: number[] = []
  for (let offset = 0; offset + 8 <= bits.length; offset += 8) {
    bytes.push(Number.parseInt(bits.slice(offset, offset + 8), 2))
  }
  return Buffer.from(bytes)
}

function currentTotp(secret: string): string {
  const counter = BigInt(Math.floor(Date.now() / 30_000))
  const message = Buffer.alloc(8)
  message.writeBigUInt64BE(counter)
  const digest = createHmac("sha1", decodeBase32(secret)).update(message).digest()
  const offset = (digest.at(-1) ?? 0) & 0x0f
  const code = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000
  return code.toString().padStart(6, "0")
}

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("load")
  await page.waitForTimeout(600)
}

async function capture(page: Page, name: string): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 })
  await settle(page)
  await page.screenshot({ path: path.join(shotsDir, `${name}-desktop.png`), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await settle(page)
  await page.screenshot({ path: path.join(shotsDir, `${name}-mobile.png`), fullPage: true })
  await page.setViewportSize({ width: 1440, height: 900 })
}

test("capture tenant pages", async ({ page }) => {
  await mkdir(shotsDir, { recursive: true })
  const stamp = Date.now()
  const companyName = `UI 审计企业 ${stamp}`

  await page.goto("/register")
  await page.getByLabel("邮箱").fill(`ui-audit-${stamp}@example.com`)
  await page.getByLabel("密码").fill(password)
  await page.getByLabel("显示名称").fill("UI 审计用户")
  await page.getByRole("button", { name: "创建账户" }).click()
  await page.waitForURL("/")

  await page.goto("/companies")
  await page.getByLabel("企业名称").fill(companyName)
  await page.getByRole("button", { name: "创建企业" }).click()
  await page.waitForURL(/\/companies\/[0-9a-f-]+$/)
  const companyUrl = page.url()

  await page.goto("/jobs")
  await page.getByText("请选择企业").click()
  await page.getByRole("option", { name: companyName }).click()
  await page.getByLabel("职位名称").fill("高级后端工程师")
  await page.getByRole("button", { name: "创建职位" }).click()
  await page.waitForURL(/\/jobs\/[0-9a-f-]+$/)
  const jobUrl = page.url()

  await page.getByRole("tab", { name: /材料/ }).click()
  await page.setInputFiles("#file", {
    name: "jd.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("负责分布式系统设计与实现，熟悉 Go 与 PostgreSQL。"),
  })
  await page.getByRole("button", { name: "上传材料", exact: true }).click()
  await page.waitForLoadState("networkidle")

  const pages: Array<[string, string]> = [
    ["home", "/"],
    ["members", "/members"],
    ["companies", "/companies"],
    ["company-detail", companyUrl],
    ["jobs", "/jobs"],
    ["job-detail", jobUrl],
    ["usage", "/usage"],
    ["settings-security", "/settings/security"],
    ["invite-invalid", "/invite/bogus-token"],
  ]
  for (const [name, url] of pages) {
    await page.goto(url)
    await capture(page, name)
  }

  await page.goto("/")
  await page.setViewportSize({ width: 390, height: 844 })
  await settle(page)
  await page.getByRole("button", { name: "打开导航菜单" }).click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(shotsDir, "nav-mobile-open.png") })
})

test("capture auth pages", async ({ page }) => {
  await mkdir(shotsDir, { recursive: true })
  for (const [name, url] of [
    ["login", "/login"],
    ["register", "/register"],
  ] as Array<[string, string]>) {
    await page.goto(url)
    await capture(page, name)
  }
})

test("capture admin pages", async ({ page }) => {
  await mkdir(shotsDir, { recursive: true })

  let secret: string | undefined
  try {
    secret = (JSON.parse(await readFile(adminStatePath, "utf8")) as { secret?: string }).secret
  } catch {
    secret = undefined
  }

  if (secret) {
    await page.goto("/login")
    await page.getByLabel("邮箱").fill(adminEmail)
    await page.getByLabel("密码").fill(password)
    await page.getByRole("button", { name: "登录" }).click()
    await page.waitForURL(/\/login\/mfa/)
    await page.locator("#code_value").fill(currentTotp(secret))
    await page.getByRole("button", { name: "验证并登录" }).click()
    await page.waitForURL(/^(?!.*\/login).*$/)
  } else {
    await page.goto("/register")
    await page.getByLabel("邮箱").fill(adminEmail)
    await page.getByLabel("密码").fill(password)
    await page.getByLabel("显示名称").fill("UI 审计管理员")
    await page.getByRole("button", { name: "创建账户" }).click()
    await page.waitForURL(/\/admin/)

    await page.goto("/settings/security")
    await page.getByRole("button", { name: "设置两步验证" }).click()
    const rendered = (
      await page.locator("text=手动输入密钥：").locator("span").textContent()
    )?.trim()
    if (!rendered) throw new Error("MFA setup secret was not rendered")
    secret = rendered
    await page.getByLabel("验证码").fill(currentTotp(secret))
    await page.getByRole("button", { name: "启用两步验证" }).click()
    await expect(page.getByRole("button", { name: "停用两步验证" })).toBeVisible()
    await writeFile(adminStatePath, JSON.stringify({ email: adminEmail, secret }), "utf8")
  }

  await page.goto("/admin")
  await capture(page, "admin")

  const tenantHref = await page.locator("a[href^='/admin/tenants/']").first().getAttribute("href")
  if (tenantHref) {
    await page.goto(tenantHref)
    await capture(page, "admin-tenant-detail")
  }

  await page.goto("/admin/orders")
  await capture(page, "admin-orders")

  await page.goto("/admin/llm-calls")
  await capture(page, "admin-llm-calls")
  const callHref = await page.locator("a[href^='/admin/llm-calls/']").first().getAttribute("href")
  if (callHref) {
    await page.goto(callHref)
    await capture(page, "admin-llm-call-detail")
  }

  await page.goto("/admin/llm-configuration")
  await capture(page, "admin-llm-configuration")
})
