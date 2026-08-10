import { render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { listAdminOrders } from "@/lib/admin-client"
import { loadAuthSession } from "@/lib/auth-client"
import AdminOrdersPage from "../src/app/(product)/admin/orders/page"

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: () => ({ value: "session-token" }),
  }),
}))

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}))

vi.mock("@/lib/auth-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-client")>()
  return {
    ...actual,
    createAuthTransport: vi.fn(() => ({})),
    loadAuthSession: vi.fn(),
  }
})

vi.mock("@/lib/admin-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/admin-client")>()
  return {
    ...actual,
    createAdminTransport: vi.fn(() => ({})),
    listAdminOrders: vi.fn(),
  }
})

const mockedLoadAuthSession = vi.mocked(loadAuthSession)
const mockedListAdminOrders = vi.mocked(listAdminOrders)

beforeEach(() => {
  vi.clearAllMocks()
})

const pendingOrder = {
  id: "order-1",
  tenant_id: "tenant-1",
  plan_code: "standard",
  plan_version: 1,
  amount_cents: 19900,
  payment_reference: "PAY-20260801-001",
  payment_channel: "offline",
  payer_note: "对公转账",
  status: "pending",
  idempotency_key: "9f1c2a40-9c0a-4d6f-9d4b-0f6b1d2a3c4e",
  submitted_by: "user-1",
  reviewed_by: null,
  reviewed_at: null,
  review_note: "",
  created_at: "2026-08-01T08:00:00+00:00",
} as const

function stubSession(isPlatformAdmin: boolean) {
  mockedLoadAuthSession.mockResolvedValue({
    kind: "authenticated",
    renewedSession: null,
    view: {
      permissions: [],
      role: null,
      tenant: null,
      user: {
        display_name: "管理员",
        email: "admin@example.com",
        id: "user-admin",
        is_platform_admin: isPlatformAdmin,
      },
    },
  })
}

function renderPage(searchParams: Record<string, string> = {}) {
  return AdminOrdersPage({ searchParams: Promise.resolve(searchParams) })
}

test("renders the order table with review actions for pending orders", async () => {
  // Given an authenticated platform admin and a pending order from the API
  stubSession(true)
  mockedListAdminOrders.mockResolvedValue({ kind: "ok", orders: [pendingOrder] })

  // When the orders page renders
  render(await renderPage())

  // Then the order row shows tenant, plan, amount, reference and status
  expect(screen.getByRole("heading", { name: "订单审核" })).toBeInTheDocument()
  const row = screen.getByText("tenant-1").closest("tr")
  expect(row?.textContent).toContain("standard v1")
  expect(row?.textContent).toContain("199.00 元")
  expect(row?.textContent).toContain("PAY-20260801-001")
  expect(row?.textContent).toContain("待确认")

  // And the pending row exposes the review actions
  expect(screen.getByRole("button", { name: "确认付款" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "拒绝" })).toBeInTheDocument()
})

test("forwards the status filter to the admin client", async () => {
  // Given an authenticated platform admin
  stubSession(true)
  mockedListAdminOrders.mockResolvedValue({ kind: "ok", orders: [] })

  // When the page renders with a status filter
  render(await renderPage({ status: "confirmed" }))

  // Then the filter reaches the admin client
  expect(mockedListAdminOrders).toHaveBeenCalledWith(
    expect.anything(),
    "session-token",
    "confirmed",
  )
  expect(screen.getByText("没有符合条件的订单。")).toBeInTheDocument()
})

test("denies the page to a non-admin user without calling the admin API", async () => {
  // Given an authenticated tenant user without the platform admin flag
  stubSession(false)

  // When the orders page renders
  render(await renderPage())

  // Then the forbidden notice shows and no admin request is made
  expect(screen.getByText("你没有访问平台管理控制台的权限。")).toBeInTheDocument()
  expect(mockedListAdminOrders).not.toHaveBeenCalled()
})
