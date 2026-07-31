import { render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { loadAuthSession } from "@/lib/auth-client"
import { loadBillingSummary } from "@/lib/billing-client"
import type { BillingSummary } from "@/lib/billing-contract"
import UsagePage from "../src/app/usage/page"

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: () => ({ value: "session-token" }),
  }),
}))

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}))

vi.mock("@/components/account-panel", () => ({
  AccountPanel: () => null,
}))

vi.mock("@/lib/auth-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-client")>()
  return {
    ...actual,
    createAuthTransport: vi.fn(() => ({})),
    loadAuthSession: vi.fn(),
  }
})

vi.mock("@/lib/billing-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/billing-client")>()
  return {
    ...actual,
    createBillingTransport: vi.fn(() => ({})),
    loadBillingSummary: vi.fn(),
  }
})

const mockedLoadAuthSession = vi.mocked(loadAuthSession)
const mockedLoadBillingSummary = vi.mocked(loadBillingSummary)

beforeEach(() => {
  vi.clearAllMocks()
})

const summaryBody: BillingSummary = {
  plan: { code: "trial", name: "试用套餐", version: 1 },
  status: "trialing",
  trial_ends_at: "2026-08-14T08:00:00+00:00",
  current_period_start: "2026-07-31T08:00:00+00:00",
  current_period_end: "2026-08-14T08:00:00+00:00",
  metrics: [
    { metric: "owners", limit: 1, used: 0, reserved: 0, remaining: 1 },
    { metric: "companies", limit: 1, used: 0, reserved: 0, remaining: 1 },
    { metric: "active_jobs", limit: 2, used: 0, reserved: 0, remaining: 2 },
    { metric: "searches", limit: 20, used: 0, reserved: 0, remaining: 20 },
    { metric: "matches", limit: 3, used: 0, reserved: 0, remaining: 3 },
    { metric: "reports", limit: 1, used: 0, reserved: 0, remaining: 1 },
  ],
}

function stubSession(permissions: readonly string[]) {
  mockedLoadAuthSession.mockResolvedValue({
    kind: "authenticated",
    renewedSession: null,
    view: {
      permissions: [...permissions],
      role: "owner",
      tenant: { id: "tenant-1", name: "示例租户", slug: "demo" },
      user: {
        display_name: "张三",
        email: "owner@example.com",
        id: "user-owner",
        is_platform_admin: false,
      },
    },
  })
}

test("renders the plan, trial expiry, and all six metric rows", async () => {
  // Given a session with the billing:read permission and a trialing subscription
  stubSession(["billing:read"])
  mockedLoadBillingSummary.mockResolvedValue({ kind: "ok", summary: summaryBody })

  // When the usage page renders
  render(await UsagePage())

  // Then the plan, status, trial expiry, and period are visible
  expect(screen.getByRole("heading", { name: "用量与套餐" })).toBeInTheDocument()
  expect(screen.getByText(/试用套餐 v1/)).toBeInTheDocument()
  expect(screen.getByText("试用中")).toBeInTheDocument()
  expect(screen.getByText(/试用到期时间/)).toBeInTheDocument()
  expect(screen.getByText(/当前计费周期/)).toBeInTheDocument()

  // And every metric row shows its label and balance
  for (const metric of summaryBody.metrics) {
    const row = screen
      .getByText(
        {
          active_jobs: "活跃职位",
          companies: "企业",
          matches: "匹配次数",
          owners: "所有者",
          reports: "报告份数",
          searches: "搜索次数",
        }[metric.metric],
      )
      .closest("tr")
    expect(row?.textContent).toContain(String(metric.limit))
    expect(row?.textContent).toContain(String(metric.remaining))
  }
  expect(screen.getAllByRole("cell", { name: "20" })).toHaveLength(2)
})

test("shows the no-subscription notice when the tenant has none", async () => {
  stubSession(["billing:read"])
  mockedLoadBillingSummary.mockResolvedValue({ kind: "notFound" })

  render(await UsagePage())

  expect(screen.getByText("当前租户暂无订阅")).toBeInTheDocument()
})

test("denies the page without the billing:read permission", async () => {
  stubSession([])

  render(await UsagePage())

  expect(screen.getByText("你没有查看用量与套餐的权限。")).toBeInTheDocument()
  expect(mockedLoadBillingSummary).not.toHaveBeenCalled()
})
