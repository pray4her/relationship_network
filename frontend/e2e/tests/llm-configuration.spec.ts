import { expect, test } from "@playwright/test"

import {
  apiJson,
  enableLlmConfiguration,
  isAuthApiAvailable,
  registerOwner,
  submitLlmAttempt,
} from "./helpers"

test("platform admin probes, enables, cancels, and restores LLM configurations", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000)
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过 LLM 配置流程")
  const adminEmail = `llm-e2e-admin-${testInfo.project.name}@example.com`
  await enableLlmConfiguration(page, { adminEmail, model: "test/success" })
  await page.reload()
  await expect(page.getByText("test/success").first()).toBeVisible()
  await expect(page.getByText("job-requirement-prompt-v2").first()).toBeVisible()
  await expect(page.getByText("search-interpretation-prompt-v1").first()).toBeVisible()
  await testInfo.attach("llm-configuration-enabled", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })

  await page.goto("/admin/llm-calls?call_type=config_probe&outcome=succeeded")
  await expect(page.getByRole("heading", { name: "LLM 调用记录" })).toBeVisible()
  const successfulCall = page.getByRole("row").filter({ hasText: "test/success" }).first()
  await expect(successfulCall.getByText("成功", { exact: true })).toBeVisible()
  await successfulCall.getByRole("link").click()
  await expect(page.getByRole("heading", { name: "LLM 调用详情" })).toBeVisible()
  await page.getByRole("button", { name: "查看原始响应" }).click()
  await expect(page.getByRole("dialog").locator("pre")).toContainText("fake-openrouter-request")

  await page.goto("/admin")
  await expect(page.getByRole("cell", { name: "llm_raw_response.view" }).first()).toBeVisible()

  await page.goto("/admin/llm-configuration")
  const failedAttempt = await submitLlmAttempt(page, { model: "test/server-error" })
  expect(failedAttempt.status).toBe("failed")
  await page.goto("/admin/llm-calls?call_type=config_probe&outcome=failed")
  await expect(page.getByRole("heading", { name: "LLM 调用记录" })).toBeVisible()
  await expect(page.getByRole("row").filter({ hasText: "test/server-error" }).first()).toBeVisible()

  await page.goto("/admin/llm-configuration")
  const delayedWorkspace = await apiJson(page, "GET", "/admin/llm-configuration")
  const delayedCurrent = delayedWorkspace.body as { current: { id: string } }
  const delayedAttempt = await apiJson(page, "POST", "/admin/llm-configuration-attempts", {
    call_bindings: {
      job_requirement_parsing: {
        prompt_version_id: "job-requirement-prompt-v2",
        request_timeout_seconds: 180,
      },
      search_interpretation: {
        prompt_version_id: "search-interpretation-prompt-v1",
        request_timeout_seconds: 15,
      },
    },
    expected_current_version_id: delayedCurrent.current.id,
    model: "test/delayed-success",
  })
  expect(delayedAttempt.status).toBe(202)
  const delayedAttemptId = (delayedAttempt.body as { id: string }).id
  const cancelled = await apiJson(
    page,
    "POST",
    `/admin/llm-configuration-attempts/${delayedAttemptId}/cancel`,
  )
  expect(cancelled.status).toBe(200)
  expect((cancelled.body as { status: string }).status).toBe("cancelled")
  await page.reload()
  await expect(page.getByText("test/success").first()).toBeVisible()

  const workspace = await apiJson(page, "GET", "/admin/llm-configuration")
  expect(workspace.status).toBe(200)
  const current = workspace.body as { current: { id: string } }
  const first = await apiJson(page, "POST", "/admin/llm-configuration-attempts", {
    call_bindings: {
      job_requirement_parsing: {
        prompt_version_id: "job-requirement-prompt-v2",
        request_timeout_seconds: 180,
      },
      search_interpretation: {
        prompt_version_id: "search-interpretation-prompt-v1",
        request_timeout_seconds: 15,
      },
    },
    expected_current_version_id: current.current.id,
    model: "test/delayed-success",
  })
  const second = await apiJson(page, "POST", "/admin/llm-configuration-attempts", {
    call_bindings: {
      job_requirement_parsing: {
        prompt_version_id: "job-requirement-prompt-v2",
        request_timeout_seconds: 180,
      },
      search_interpretation: {
        prompt_version_id: "search-interpretation-prompt-v1",
        request_timeout_seconds: 15,
      },
    },
    expected_current_version_id: current.current.id,
    model: "test/success",
  })
  expect(first.status).toBe(202)
  expect(second.status).toBe(409)
  const firstBody = first.body as { id: string }
  await apiJson(page, "POST", `/admin/llm-configuration-attempts/${firstBody.id}/cancel`)

  await page.goto("/admin/llm-configuration")
  await page
    .getByRole("row")
    .filter({ hasText: "test/success" })
    .getByRole("button", { name: "复制并探测" })
    .first()
    .click()
  await page.getByRole("alertdialog").getByRole("button", { name: "复制并探测" }).click()
  await expect(page.getByText("已启用", { exact: true })).toBeVisible({ timeout: 30_000 })
  await page.getByLabel("OpenRouter 模型").fill("test/success")
  await page.locator("#job-requirement-prompt-version").selectOption("job-requirement-prompt-v2")
  await page.getByRole("button", { name: "提交并探测全部调用类型" }).click()
  await expect(page.getByText("已启用", { exact: true })).toBeVisible({ timeout: 30_000 })
})

test("tenant member cannot access LLM call diagnostics", async ({ page }, testInfo) => {
  const email = `llm-e2e-member-${testInfo.project.name}-${Date.now()}@example.com`
  await registerOwner(page, { displayName: "LLM E2E 普通成员", email })
  await page.waitForURL("/")

  await page.goto("/admin/llm-calls")
  await expect(page.getByRole("heading", { name: "LLM 调用记录" })).toBeVisible()
  await expect(page.getByText("你没有访问平台管理控制台的权限。")).toBeVisible()
})

test("tenant member cannot access LLM configuration", async ({ page }, testInfo) => {
  const email = `llm-e2e-config-member-${testInfo.project.name}-${Date.now()}@example.com`
  await registerOwner(page, { displayName: "LLM 配置普通成员", email })
  await page.waitForURL("/")

  await page.goto("/admin/llm-configuration")
  await expect(page.getByRole("heading", { name: "LLM 配置" })).toBeVisible()
  await expect(page.getByText("你没有访问平台管理控制台的权限。")).toBeVisible()
})
