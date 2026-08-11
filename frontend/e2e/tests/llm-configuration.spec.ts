import { createHmac } from "node:crypto"

import { expect, test } from "@playwright/test"

const PASSWORD = "e2e-password-1"

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

test("platform admin probes, enables, cancels, and restores LLM configurations", async ({
  page,
}, testInfo) => {
  const adminEmail = `llm-e2e-admin-${testInfo.project.name}@example.com`
  await page.goto("/register")
  await page.getByLabel("邮箱").fill(adminEmail)
  await page.getByLabel("密码").fill(PASSWORD)
  await page.getByLabel("显示名称").fill("LLM E2E 管理员")
  await page.getByRole("button", { name: "创建账户" }).click()
  await page.waitForURL("/admin")

  await page.goto("/settings/security")
  await page.getByRole("button", { name: "设置两步验证" }).click()
  const secret = (await page.locator("text=手动输入密钥：").locator("span").textContent())?.trim()
  if (!secret) throw new Error("MFA setup secret was not rendered")
  await page.getByLabel("验证码").fill(currentTotp(secret))
  await page.getByRole("button", { name: "启用两步验证" }).click()
  await expect(page.getByRole("button", { name: "停用两步验证" })).toBeVisible()

  await page.goto("/admin/llm-configuration")
  await expect(page.getByRole("heading", { name: "LLM 配置" })).toBeVisible()
  await page.getByLabel("OpenRouter 模型").fill("test/success")
  await page.getByRole("button", { name: "提交并探测" }).click()
  await expect(page.getByText("已启用", { exact: true })).toBeVisible({ timeout: 15_000 })
  await page.reload()
  await expect(page.getByText("test/success").first()).toBeVisible()

  await page.getByLabel("OpenRouter 模型").fill("test/delayed-success")
  await page.getByRole("button", { name: "提交并探测" }).click()
  await page.getByRole("button", { name: "取消变更" }).click()
  await page.getByRole("button", { name: "确认取消" }).click()
  await expect(page.getByText("已取消", { exact: true })).toBeVisible({ timeout: 15_000 })

  await page.getByRole("button", { name: "复制并探测" }).last().click()
  await page.getByRole("button", { name: "复制并探测" }).last().click()
  await expect(page.getByText("已启用", { exact: true })).toBeVisible({ timeout: 15_000 })
})
