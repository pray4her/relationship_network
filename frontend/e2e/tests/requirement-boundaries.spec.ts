import { expect, test } from "@playwright/test"

import {
  apiJson,
  archiveJob,
  createCompanyAndJob,
  ensureReadyLlmConfiguration,
  expireTenantSubscription,
  isAuthApiAvailable,
  jobIdFromUrl,
  loadRequirementWorkspace,
  registerOwner,
  saveDraftResearchTopicFrom,
  selectRequirementSources,
  waitForRequirementDraft,
} from "./helpers"

test("requirement boundary matrix", async ({ browser, context, page }, testInfo) => {
  test.setTimeout(180_000)
  test.skip(
    testInfo.project.name !== "chrome",
    "边界矩阵仅在 Chrome 全量执行，Edge 以主路径截图为证",
  )
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过边界矩阵")
  await ensureReadyLlmConfiguration(browser, { projectName: testInfo.project.name })
  const stamp = Date.now()
  const ownerEmail = `req-bound-${testInfo.project.name}-${stamp}@example.com`
  await registerOwner(page, { displayName: "边界租户主", email: ownerEmail })
  await page.waitForURL("/")
  const { jobUrl } = await createCompanyAndJob(page, { stamp, title: "边界矩阵职位" })
  const jobPath = new URL(jobUrl).pathname

  await page.getByRole("tab", { name: /需求草稿/ }).click()
  const region = page.getByRole("region", { name: "职位需求草稿" })
  await expect(region.getByText("生成配置尚未就绪")).toHaveCount(0)
  await selectRequirementSources(page)
  await region.getByRole("button", { name: "生成职位需求草稿" }).click()
  await expect(region.getByText("生成成功", { exact: true })).toBeVisible({ timeout: 60_000 })
  await waitForRequirementDraft(page)
  const jobId = jobIdFromUrl(page)
  const workspace = await loadRequirementWorkspace(page, jobId)
  if (workspace.draft === null) {
    throw new Error("generated draft was missing")
  }

  const page2 = await context.newPage()
  await page2.goto(`${jobPath}?tab=requirement`)
  await expect(page2.getByRole("heading", { name: "审阅职位需求草稿" })).toBeVisible()
  const firstSave = await saveDraftResearchTopicFrom(
    page,
    jobId,
    workspace.draft,
    "第一标签修订主题",
  )
  expect(firstSave.status).toBe(200)
  const staleSave = await saveDraftResearchTopicFrom(
    page2,
    jobId,
    workspace.draft,
    "第二标签过期修订",
  )
  expect(staleSave.status).toBe(409)
  await page2.reload()
  await expect(page2.getByRole("heading", { name: "审阅职位需求草稿" })).toBeVisible()
  await expect(page2.locator("#draft-field-research_topic_query")).toHaveValue("第一标签修订主题")
  await page2.close()

  await page.reload()
  await waitForRequirementDraft(page)
  await expect(page.locator("#draft-field-research_topic_query")).toHaveValue("第一标签修订主题")
  await expect(page.getByText("已保存", { exact: true })).toBeVisible()
  await testInfo.attach("requirement-refresh-restore", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })

  await page.getByRole("tab", { name: "概览" }).click()
  await archiveJob(page, jobId)
  await page.reload()
  await expect(page.getByText("已归档", { exact: true })).toBeVisible({ timeout: 15_000 })
  await page.getByRole("tab", { name: /需求草稿/ }).click()
  await expect(page.getByRole("button", { name: "生成职位需求草稿" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "确认版本" })).toHaveCount(0)
  await page.getByRole("tab", { name: /版本/ }).click()
  await expect(page.getByRole("button", { name: "复制为新草稿" })).toHaveCount(0)
  await testInfo.attach("requirement-archived-readonly", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })

  const viewerEmail = `req-viewer-${testInfo.project.name}-${stamp}@example.com`
  const role = await apiJson(page, "POST", "/roles", {
    description: "只读职位",
    name: "职位只读",
    permissions: ["jobs:read", "companies:read"],
  })
  expect(role.status).toBe(201)
  const roleId = (role.body as { id: string }).id
  const invited = await apiJson(page, "POST", "/invitations", { email: viewerEmail })
  expect(invited.status).toBe(201)
  const inviteUrl = (invited.body as { invite_url: string }).invite_url
  expect(inviteUrl).toContain("/invite/")

  const viewer = await browser.newContext()
  const viewerPage = await viewer.newPage()
  await viewerPage.goto(inviteUrl.trim())
  await viewerPage.getByLabel("密码").fill("e2e-password-1")
  await viewerPage.getByLabel("显示名称").fill("只读成员")
  await viewerPage.getByRole("button", { name: "注册并接受邀请" }).click()
  await viewerPage.waitForURL(/\/$/)
  const members = await apiJson(page, "GET", "/members")
  expect(members.status).toBe(200)
  const viewerMember = (members.body as { email: string; membership_id: string }[]).find(
    (member) => member.email === viewerEmail,
  )
  if (viewerMember === undefined) throw new Error("viewer membership was not created")
  const assigned = await apiJson(page, "PUT", `/members/${viewerMember.membership_id}/roles`, {
    role_ids: [roleId],
  })
  expect(assigned.status).toBe(200)
  await viewerPage.goto(jobPath)
  await expect(viewerPage.getByRole("button", { name: "生成职位需求草稿" })).toHaveCount(0)
  await expect(viewerPage.getByRole("button", { name: "确认版本" })).toHaveCount(0)
  await viewer.close()

  expireTenantSubscription(ownerEmail)
  await page.goto(jobPath)
  await expect(page.getByText("订阅已到期，当前处于只读模式")).toBeVisible()
  await testInfo.attach("requirement-subscription-readonly", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})
