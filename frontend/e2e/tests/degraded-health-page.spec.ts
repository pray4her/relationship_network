import { expect, test } from "@playwright/test"

test("shows the unavailable dependency while the API remains online", async ({
  page,
}, testInfo) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "部分服务不可用" })).toBeVisible()
  await expect(
    page.getByRole("article").filter({ hasText: "FastAPI" }).getByText("在线"),
  ).toBeVisible()
  await expect(
    page.getByRole("article").filter({ hasText: "MinIO 对象存储" }).getByText("离线"),
  ).toBeVisible()
  await expect(page.getByText("API 暂时无法连接")).toHaveCount(0)

  await testInfo.attach("degraded-health-dashboard", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})
