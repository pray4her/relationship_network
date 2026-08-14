import { expect, test } from "@playwright/test"

import {
  activateJob,
  cancelInFlightRequirementTask,
  copyCurrentRequirementVersion,
  createCompanyAndJob,
  ensureReadyLlmConfiguration,
  isAuthApiAvailable,
  JOB_DESCRIPTION,
  jobIdFromUrl,
  registerOwner,
  saveDraftResearchTopic,
  selectRequirementSources,
  waitForRequirementDraft,
} from "./helpers"

test("tenant corrects sources, generates a draft, and confirms v1 then v2", async ({
  browser,
  page,
}, testInfo) => {
  test.setTimeout(240_000)
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过职位需求解析流程")
  await ensureReadyLlmConfiguration(browser, { projectName: testInfo.project.name })
  const stamp = Date.now()
  const email = `req-e2e-${testInfo.project.name}-${stamp}@example.com`
  await registerOwner(page, { displayName: "解析租户主", email })
  await page.waitForURL("/")
  await createCompanyAndJob(page, { stamp })
  const jobId = jobIdFromUrl(page)

  await page.getByRole("tab", { name: /需求草稿/ }).click()
  const region = page.getByRole("region", { name: "职位需求草稿" })
  await expect(region.getByRole("group", { name: "职位描述" })).toBeVisible()
  await expect(region.getByText("生成配置尚未就绪")).toHaveCount(0)
  await region
    .locator("#requirement-correction-job-description")
    .fill(`${JOB_DESCRIPTION} 补充海外经历。`)
  await selectRequirementSources(page)
  await region.getByRole("button", { name: "生成职位需求草稿" }).click()
  await expect(region.getByText("生成成功", { exact: true })).toBeVisible({ timeout: 60_000 })
  await waitForRequirementDraft(page)
  await testInfo.attach("requirement-draft", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })

  await region.getByRole("button", { name: "确认版本" }).click()
  await page.getByRole("alertdialog").getByRole("button", { name: "确认版本" }).click()
  await expect(page.getByRole("alertdialog")).toHaveCount(0)
  await page.getByRole("tab", { name: "需求版本" }).click()
  await expect(page.getByRole("cell", { name: /^v1/ })).toBeVisible({ timeout: 15_000 })

  await copyCurrentRequirementVersion(page, jobId)
  await saveDraftResearchTopic(page, jobId, "人工智能与计算社会科学")
  await waitForRequirementDraft(page)
  await expect(page.locator("#draft-field-research_topic_query")).toHaveValue(
    "人工智能与计算社会科学",
  )
  await page.getByRole("button", { name: "确认版本" }).click()
  await page.getByRole("alertdialog").getByRole("button", { name: "确认版本" }).click()
  await expect(page.getByRole("alertdialog")).toHaveCount(0)
  await page.getByRole("tab", { name: "需求版本" }).click()
  await expect(page.getByRole("cell", { name: /^v2/ })).toBeVisible({ timeout: 15_000 })

  await page.getByRole("tab", { name: "概览" }).click()
  await activateJob(page, jobId)
  await page.reload()
  await expect(page.getByText("活跃", { exact: true })).toBeVisible({ timeout: 15_000 })
  await testInfo.attach("requirement-v2", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})

test("tenant cancels an in-flight generation", async ({ browser, page }, testInfo) => {
  test.setTimeout(240_000)
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过取消解析流程")
  await ensureReadyLlmConfiguration(browser, {
    model: "test/delayed-success",
    projectName: testInfo.project.name,
  })
  const stamp = Date.now()
  const email = `req-cancel-${testInfo.project.name}-${stamp}@example.com`
  await registerOwner(page, { displayName: "取消解析租户主", email })
  await page.waitForURL("/")
  await createCompanyAndJob(page, { stamp, title: "取消解析职位" })
  const jobId = jobIdFromUrl(page)
  await page.getByRole("tab", { name: /需求草稿/ }).click()
  const region = page.getByRole("region", { name: "职位需求草稿" })
  await selectRequirementSources(page)
  await region.getByRole("button", { name: "生成职位需求草稿" }).click()
  await cancelInFlightRequirementTask(page, jobId)
  await page.reload()
  await page.getByRole("tab", { name: "需求草稿", exact: true }).click()
  await expect(page.getByText("已取消", { exact: true })).toBeVisible({ timeout: 20_000 })
  await testInfo.attach("requirement-cancelled", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
  await ensureReadyLlmConfiguration(browser, { projectName: testInfo.project.name })
})
