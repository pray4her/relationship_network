import { expect, test } from "@playwright/test"

test("shows live dependency status from the API", async ({ page }, testInfo) => {
  const failedResponses: string[] = []
  const pageErrors: string[] = []

  page.on("pageerror", (error) => pageErrors.push(error.message))
  page.on("response", (response) => {
    if (!response.ok()) {
      failedResponses.push(`${response.status()} ${response.url()}`)
    }
  })

  await page.goto("/")

  await expect(page.getByRole("heading", { name: "系统运行正常" })).toBeVisible()
  await expect(page.getByText("FastAPI")).toBeVisible()
  await expect(page.getByText("PostgreSQL")).toBeVisible()
  await expect(page.getByText("Redis")).toBeVisible()
  await expect(page.getByText("MinIO 对象存储")).toBeVisible()
  await expect(page.getByText("在线")).toHaveCount(4)

  await testInfo.attach("health-dashboard", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })

  expect(pageErrors).toEqual([])
  expect(failedResponses).toEqual([])
})

for (const width of [320, 375]) {
  test(`keeps the Chinese readiness heading on one line at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 })
    await page.goto("/")

    const heading = page.getByRole("heading", { name: "系统运行正常" })
    await expect(heading).toBeVisible()
    const bounds = await heading.boundingBox()

    expect(bounds).not.toBeNull()
    expect(bounds?.height).toBeLessThan(65)
  })
}
