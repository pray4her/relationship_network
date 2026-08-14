import { execFileSync } from "node:child_process"
import { createHmac } from "node:crypto"
import { existsSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { type Browser, expect, type Page } from "@playwright/test"

export const PASSWORD = "e2e-password-1"
export const JOB_DESCRIPTION = "需要海外华人，H 指数至少 30，研究人工智能。"
export const apiBaseUrl = process.env["API_INTERNAL_URL"] ?? "http://localhost:8000"

export async function isAuthApiAvailable(): Promise<boolean> {
  try {
    const response = await fetch(new URL("/auth/me", apiBaseUrl))
    return response.status === 401
  } catch {
    return false
  }
}

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

export function currentTotp(secret: string): string {
  const counter = BigInt(Math.floor(Date.now() / 30_000))
  const message = Buffer.alloc(8)
  message.writeBigUInt64BE(counter)
  const digest = createHmac("sha1", decodeBase32(secret)).update(message).digest()
  const offset = (digest.at(-1) ?? 0) & 0x0f
  const code = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000
  return code.toString().padStart(6, "0")
}

export async function registerOwner(
  page: Page,
  options: { email: string; displayName: string },
): Promise<void> {
  await page.goto("/register")
  await page.getByLabel("邮箱").fill(options.email)
  await page.getByLabel("密码").fill(PASSWORD)
  await page.getByLabel("显示名称").fill(options.displayName)
  await page.getByRole("button", { name: "创建账户" }).click()
}

export async function enableMfa(page: Page): Promise<string> {
  await page.goto("/settings/security")
  await page.getByRole("button", { name: "设置两步验证" }).click()
  const secret = (await page.locator("text=手动输入密钥：").locator("span").textContent())?.trim()
  if (!secret) throw new Error("MFA setup secret was not rendered")
  await page.getByLabel("验证码").fill(currentTotp(secret))
  await page.getByRole("button", { name: "启用两步验证" }).click()
  await expect(page.getByRole("button", { name: "停用两步验证" })).toBeVisible()
  return secret
}

export async function createCompanyAndJob(
  page: Page,
  options: { stamp: number; title?: string },
): Promise<{ companyName: string; jobUrl: string }> {
  const title = options.title ?? "研究人才负责人"
  const companyName = `E2E 解析企业 ${options.stamp}`
  const company = await apiJson(page, "POST", "/companies", { name: companyName })
  if (company.status !== 201) {
    throw new Error(`create company failed: ${company.status} ${JSON.stringify(company.body)}`)
  }
  const companyId = (company.body as { id: string }).id
  const job = await apiJson(page, "POST", "/jobs", {
    company_id: companyId,
    description: JOB_DESCRIPTION,
    title,
  })
  if (job.status !== 201) {
    throw new Error(`create job failed: ${job.status} ${JSON.stringify(job.body)}`)
  }
  const jobId = (job.body as { id: string }).id
  await page.goto(`/jobs/${jobId}`)
  await page.waitForURL(/\/jobs\/[0-9a-f-]+$/)
  return { companyName, jobUrl: page.url() }
}

export async function waitForRequirementDraft(page: Page): Promise<void> {
  const heading = page.getByRole("heading", { name: "审阅职位需求草稿" })
  await expect(async () => {
    const tab = page.getByRole("tab", { name: "需求草稿", exact: true })
    if ((await tab.count()) > 0) {
      await tab.click()
    }
    if (await heading.isVisible()) {
      return
    }
    await page.reload()
    await page.getByRole("tab", { name: "需求草稿", exact: true }).click()
    await expect(heading).toBeVisible({ timeout: 8_000 })
  }).toPass({ timeout: 45_000 })
}

export async function expectUnsavedDraft(page: Page): Promise<void> {
  await expect(page.getByText("有未保存修改", { exact: true })).toBeVisible()
}

export function jobIdFromUrl(page: Page): string {
  const match = new URL(page.url()).pathname.match(/\/jobs\/([0-9a-f-]{36})/i)
  if (match?.[1] === undefined) {
    throw new Error(`job id missing from ${page.url()}`)
  }
  return match[1]
}

type DraftCondition = {
  readonly description: string
  readonly field: string
  readonly item_id: string
  readonly operator: string
  readonly value: unknown
}

type DraftResult = {
  readonly hard_conditions: readonly DraftCondition[]
  readonly preference_conditions: readonly DraftCondition[]
  readonly research_topic_query: { readonly value: string }
  readonly source_conflicts: readonly {
    readonly item_id: string
    readonly resolution: { readonly note: string } | null
  }[]
  readonly unsupported_conditions: readonly {
    readonly description: string
    readonly item_id: string
  }[]
}

export type RequirementDraftBody = {
  readonly id: string
  readonly result: DraftResult
  readonly revision: number
}

type RequirementWorkspaceBody = {
  readonly draft: RequirementDraftBody | null
  readonly task: { readonly id: string; readonly status: string } | null
}

function submissionFromDraftResult(
  result: DraftResult,
  researchTopicQuery: string,
): Record<string, unknown> {
  const condition = (item: DraftCondition) => ({
    description: item.description,
    field: item.field,
    item_id: item.item_id,
    operator: item.operator,
    value: item.value,
  })
  return {
    hard_conditions: result.hard_conditions.map(condition),
    preference_conditions: result.preference_conditions.map(condition),
    research_topic_query: researchTopicQuery,
    source_conflicts: result.source_conflicts.map((item) => ({
      item_id: item.item_id,
      resolution_note: item.resolution?.note ?? null,
    })),
    unsupported_conditions: result.unsupported_conditions.map((item) => ({
      description: item.description,
      item_id: item.item_id,
    })),
  }
}

export async function loadRequirementWorkspace(
  page: Page,
  jobId: string,
): Promise<RequirementWorkspaceBody> {
  const response = await apiJson(page, "GET", `/jobs/${jobId}/requirement-generation`)
  if (response.status !== 200) {
    throw new Error(`workspace load failed: ${response.status} ${JSON.stringify(response.body)}`)
  }
  return response.body as RequirementWorkspaceBody
}

export async function copyCurrentRequirementVersion(page: Page, jobId: string): Promise<void> {
  const response = await apiJson(page, "POST", `/jobs/${jobId}/requirement-versions/copy-current`)
  if (response.status !== 200) {
    throw new Error(`copy failed: ${response.status} ${JSON.stringify(response.body)}`)
  }
}

export async function saveDraftResearchTopicFrom(
  page: Page,
  jobId: string,
  draft: RequirementDraftBody,
  researchTopicQuery: string,
): Promise<{ status: number; body: unknown }> {
  return apiJson(page, "PUT", `/jobs/${jobId}/requirement-drafts/${draft.id}`, {
    expected_revision: draft.revision,
    result: submissionFromDraftResult(draft.result, researchTopicQuery),
  })
}

export async function saveDraftResearchTopic(
  page: Page,
  jobId: string,
  researchTopicQuery: string,
): Promise<void> {
  const workspace = await loadRequirementWorkspace(page, jobId)
  if (workspace.draft === null) {
    throw new Error("no draft to save")
  }
  const response = await saveDraftResearchTopicFrom(
    page,
    jobId,
    workspace.draft,
    researchTopicQuery,
  )
  if (response.status !== 200) {
    throw new Error(`save failed: ${response.status} ${JSON.stringify(response.body)}`)
  }
}

export async function activateJob(page: Page, jobId: string): Promise<void> {
  const response = await apiJson(page, "POST", `/jobs/${jobId}/activate`)
  if (response.status !== 200) {
    throw new Error(`activate failed: ${response.status} ${JSON.stringify(response.body)}`)
  }
}

export async function submitLlmAttempt(
  page: Page,
  options: { model: string; promptVersionId?: string },
): Promise<{ id: string; status: string }> {
  const workspace = await apiJson(page, "GET", "/admin/llm-configuration")
  const current = workspace.body as { current: { id: string } | null }
  if (current.current === null) {
    throw new Error("no current LLM configuration")
  }
  const created = await apiJson(page, "POST", "/admin/llm-configuration-attempts", {
    call_bindings: {
      job_requirement_parsing: {
        prompt_version_id: options.promptVersionId ?? "job-requirement-prompt-v2",
        request_timeout_seconds: 180,
      },
      search_interpretation: {
        prompt_version_id: "search-interpretation-prompt-v1",
        request_timeout_seconds: 15,
      },
    },
    expected_current_version_id: current.current.id,
    model: options.model,
  })
  if (created.status !== 202) {
    throw new Error(`create attempt failed: ${created.status} ${JSON.stringify(created.body)}`)
  }
  const id = (created.body as { id: string }).id
  let status = ""
  await expect
    .poll(
      async () => {
        const attempt = await apiJson(page, "GET", `/admin/llm-configuration-attempts/${id}`)
        status = (attempt.body as { status: string }).status
        return status
      },
      { timeout: 60_000 },
    )
    .toMatch(/^(succeeded|failed|cancelled|conflicted)$/)
  return { id, status }
}

export async function cancelActiveLlmAttempt(page: Page): Promise<string> {
  await expect
    .poll(
      async () => {
        const workspace = await apiJson(page, "GET", "/admin/llm-configuration")
        const body = workspace.body as { active_attempt: { id: string } | null }
        return body.active_attempt?.id ?? ""
      },
      { timeout: 15_000 },
    )
    .not.toBe("")
  const workspace = await apiJson(page, "GET", "/admin/llm-configuration")
  const attempt = (workspace.body as { active_attempt: { id: string } | null }).active_attempt
  if (attempt === null) {
    throw new Error("active LLM configuration attempt disappeared before cancel")
  }
  const cancelled = await apiJson(
    page,
    "POST",
    `/admin/llm-configuration-attempts/${attempt.id}/cancel`,
  )
  if (cancelled.status !== 200) {
    throw new Error(`LLM cancel failed: ${cancelled.status} ${JSON.stringify(cancelled.body)}`)
  }
  const body = cancelled.body as { status?: string }
  if (body.status !== "cancelled") {
    throw new Error(`LLM cancel left status ${JSON.stringify(cancelled.body)}`)
  }
  return attempt.id
}

export async function archiveJob(page: Page, jobId: string): Promise<void> {
  const response = await apiJson(page, "POST", `/jobs/${jobId}/archive`)
  if (response.status !== 200) {
    throw new Error(`archive failed: ${response.status} ${JSON.stringify(response.body)}`)
  }
}

export async function cancelInFlightRequirementTask(page: Page, jobId: string): Promise<void> {
  await expect
    .poll(
      async () => {
        const workspace = await loadRequirementWorkspace(page, jobId)
        return workspace.task?.status ?? ""
      },
      { timeout: 15_000 },
    )
    .toMatch(/^(queued|running|retry_scheduled)$/)
  const workspace = await loadRequirementWorkspace(page, jobId)
  if (workspace.task === null) {
    throw new Error("parsing task disappeared before cancel")
  }
  const path = `/jobs/${jobId}/requirement-parsing-tasks/${workspace.task.id}/cancel`
  let cancelled = await apiJson(page, "POST", path)
  for (let attempt = 0; attempt < 4 && cancelled.status === 500; attempt += 1) {
    await new Promise((resolve) => {
      setTimeout(resolve, 250)
    })
    const latest = await loadRequirementWorkspace(page, jobId)
    if (latest.task?.status === "cancelled") {
      return
    }
    cancelled = await apiJson(page, "POST", path)
  }
  if (cancelled.status !== 200) {
    throw new Error(`cancel failed: ${cancelled.status} ${JSON.stringify(cancelled.body)}`)
  }
}

export async function selectRequirementSources(page: Page): Promise<void> {
  const region = page.getByRole("region", { name: "职位需求草稿" })
  const correction = region.locator("#requirement-correction-job-description")
  if ((await correction.count()) > 0) {
    const current = await correction.inputValue()
    if (current.trim().length === 0) {
      await correction.fill(JOB_DESCRIPTION)
    }
  }
  const box = region.getByRole("checkbox", { name: "用于生成职位需求草稿" })
  await box.scrollIntoViewIfNeeded()
  if (!(await box.isChecked())) {
    await box.click()
  }
  await expect(box).toBeChecked()
  await expect(region.getByText("已选择 0 个来源", { exact: false })).toHaveCount(0)
}

export async function sessionCookie(page: Page): Promise<string> {
  const cookies = await page.context().cookies()
  const session = cookies.find((cookie) => cookie.name === "rn_session")
  if (session === undefined) throw new Error("session cookie was not set")
  return session.value
}

export async function apiJson(
  page: Page,
  method: string,
  path: string,
  body?: unknown,
): Promise<{ status: number; body: unknown }> {
  const response = await fetch(new URL(path, apiBaseUrl), {
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: {
      cookie: `rn_session=${await sessionCookie(page)}`,
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    method,
  })
  const text = await response.text()
  let parsed: unknown = text
  if (text.length === 0) {
    parsed = null
  } else {
    try {
      parsed = JSON.parse(text) as unknown
    } catch {
      parsed = text
    }
  }
  return {
    body: parsed,
    status: response.status,
  }
}

function repoRoot(): string {
  let current = process.cwd()
  for (let index = 0; index < 5; index += 1) {
    if (existsSync(join(current, "compose.yaml"))) {
      return current
    }
    current = join(current, "..")
  }
  throw new Error("compose.yaml not found from Playwright working directory")
}

function mfaSecretPath(email: string): string {
  return join(tmpdir(), `rn-e2e-mfa-${email.replaceAll(/[^a-z0-9.-]+/gi, "_")}.txt`)
}

function readStoredMfaSecret(email: string): string | undefined {
  const path = mfaSecretPath(email)
  if (!existsSync(path)) return undefined
  const secret = readFileSync(path, "utf8").trim()
  return secret.length === 0 ? undefined : secret
}

export async function loginOwner(
  page: Page,
  options: { email: string; secret?: string },
): Promise<void> {
  await page.goto("/login")
  await page.getByLabel("邮箱").fill(options.email)
  await page.getByLabel("密码").fill(PASSWORD)
  await page.getByRole("button", { name: "登录" }).click()
  if (options.secret !== undefined) {
    await page.getByLabel("验证码或恢复码").fill(currentTotp(options.secret))
    await page.getByRole("button", { name: "验证并登录" }).click()
  }
}

export async function enableLlmConfiguration(
  page: Page,
  options: { adminEmail: string; model: string },
): Promise<void> {
  const stored = readStoredMfaSecret(options.adminEmail)
  if (stored === undefined) {
    await registerOwner(page, { displayName: "LLM E2E 管理员", email: options.adminEmail })
    const duplicate = page.getByText("该邮箱已注册，请直接登录")
    try {
      await Promise.race([
        page.waitForURL(/\/(admin|settings\/security)/, { timeout: 15_000 }),
        duplicate.waitFor({ state: "visible", timeout: 15_000 }),
      ])
    } catch {
      throw new Error(
        `platform admin ${options.adminEmail} did not reach /admin (url=${page.url()})`,
      )
    }
    if (await duplicate.isVisible()) {
      await loginOwner(page, { email: options.adminEmail })
      await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 15_000 })
    }
    if ((await page.getByRole("button", { name: "停用两步验证" }).count()) === 0) {
      const secret = await enableMfa(page)
      writeFileSync(mfaSecretPath(options.adminEmail), secret)
    }
  } else {
    await loginOwner(page, { email: options.adminEmail, secret: stored })
    await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20_000 })
  }
  await page.goto("/admin/llm-configuration")
  await expect(page.getByRole("heading", { name: "LLM 配置" })).toBeVisible()
  await page.getByLabel("OpenRouter 模型").fill(options.model)
  await page.locator("#job-requirement-prompt-version").selectOption("job-requirement-prompt-v2")
  await page
    .locator("#search-interpretation-prompt-version")
    .selectOption("search-interpretation-prompt-v1")
  await page.getByRole("button", { name: "提交并探测全部调用类型" }).click()
  await expect(page.getByText("已启用", { exact: true })).toBeVisible({ timeout: 60_000 })
}

export async function ensureReadyLlmConfiguration(
  browser: Browser,
  options: { projectName: string; model?: string },
): Promise<void> {
  const context = await browser.newContext()
  const page = await context.newPage()
  try {
    await enableLlmConfiguration(page, {
      adminEmail: `llm-e2e-admin-${options.projectName}@example.com`,
      model: options.model ?? "test/success",
    })
  } finally {
    await context.close()
  }
}

export async function expireTenantSubscription(ownerEmail: string): Promise<void> {
  const sql = `UPDATE tenant_subscriptions SET current_period_end = NOW() - INTERVAL '1 day' WHERE tenant_id IN (SELECT tm.tenant_id FROM tenant_memberships tm JOIN users u ON u.id = tm.user_id WHERE u.email = '${ownerEmail.replaceAll("'", "''")}')`
  execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "relationship",
      "-d",
      "relationship_network",
      "-c",
      sql,
    ],
    { cwd: repoRoot(), stdio: "pipe" },
  )
}
