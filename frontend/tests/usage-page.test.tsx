import { render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { loadAuthSession } from "@/lib/auth-client"
import { loadBillingSummary } from "@/lib/billing-client"
import type { BillingSummary } from "@/lib/billing-contract"
import { listOrders } from "@/lib/orders-client"
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

vi.mock("@/lib/orders-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orders-client")>()
  return {
    ...actual,
    createOrdersTransport: vi.fn(() => ({})),
    listOrders: vi.fn(),
  }
})

const mockedLoadAuthSession = vi.mocked(loadAuthSession)
const mockedLoadBillingSummary = vi.mocked(loadBillingSummary)
const mockedListOrders = vi.mocked(listOrders)

beforeEach(() => {
  vi.clearAllMocks()
  mockedListOrders.mockResolvedValue({ kind: "ok", orders: [] })
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

const pendingOrder = {
  id: "order-1",
  tenant_id: "tenant-1",
  plan_code: "standard",
  plan_version: 1,
  amount_cents: 19900,
  payment_reference: "PAY-20260801-001",
  payment_channel: "offline",
  payer_note: "",
  status: "pending",
  idempotency_key: "9f1c2a40-9c0a-4d6f-9d4b-0f6b1d2a3c4e",
  submitted_by: "user-1",
  reviewed_by: null,
  reviewed_at: null,
  review_note: "",
  created_at: "2026-08-01T08:00:00+00:00",
} as const

test("shows the read-only banner for an expired subscription", async () => {
  // Given an expired subscription
  stubSession(["billing:read", "billing:manage"])
  mockedLoadBillingSummary.mockResolvedValue({
    kind: "ok",
    summary: { ...summaryBody, status: "expired" },
  })

  // When the usage page renders
  render(await UsagePage())

  // Then the read-only banner is visible and the cancel action is not offered
  expect(screen.getByText(/只读模式/)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "取消订阅" })).not.toBeInTheDocument()
})

test("shows the cancel action and the offline order form for a trialing manager", async () => {
  // Given a trialing subscription and the billing:manage permission
  stubSession(["billing:read", "billing:manage"])
  mockedLoadBillingSummary.mockResolvedValue({ kind: "ok", summary: summaryBody })

  // When the usage page renders
  render(await UsagePage())

  // Then the cancel button, the order form and the order history section are visible
  expect(screen.getByRole("button", { name: "取消订阅" })).toBeInTheDocument()
  expect(screen.getByRole("heading", { name: "申请订阅（线下付款）" })).toBeInTheDocument()
  expect(screen.getByLabelText("付款凭证号")).toBeInTheDocument()
  expect(screen.getByRole("heading", { name: "我的订单" })).toBeInTheDocument()
  expect(screen.getByText("暂无订单记录。")).toBeInTheDocument()
})

test("shows the cancellation request and hides the cancel action once requested", async () => {
  // Given an active subscription with a pending cancellation request
  stubSession(["billing:read", "billing:manage"])
  mockedLoadBillingSummary.mockResolvedValue({
    kind: "ok",
    summary: {
      ...summaryBody,
      cancel_requested_at: "2026-08-03T08:00:00+00:00",
      offline_order_id: "order-1",
      status: "active",
    },
  })

  // When the usage page renders
  render(await UsagePage())

  // Then the cancellation schedule is shown and the cancel button is gone
  expect(screen.getByText(/申请取消/)).toBeInTheDocument()
  expect(screen.getByText(/到期后取消/)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "取消订阅" })).not.toBeInTheDocument()
})

test("renders the order history rows with status tags", async () => {
  // Given a submitted offline order
  stubSession(["billing:read"])
  mockedLoadBillingSummary.mockResolvedValue({ kind: "ok", summary: summaryBody })
  mockedListOrders.mockResolvedValue({ kind: "ok", orders: [pendingOrder] })

  // When the usage page renders
  render(await UsagePage())

  // Then the order row shows the plan, amount, reference and status tag
  const row = screen.getByText("PAY-20260801-001").closest("tr")
  expect(row?.textContent).toContain("standard v1")
  expect(row?.textContent).toContain("199.00 元")
  expect(row?.textContent).toContain("待确认")
})
