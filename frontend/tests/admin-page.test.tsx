import { render, screen } from "@testing-library/react"
import { redirect } from "next/navigation"
import { beforeEach, expect, test, vi } from "vitest"

import { loadAdminAuditEvents, searchAdminTenants } from "@/lib/admin-client"
import { loadAuthSession } from "@/lib/auth-client"
import AdminPage from "../src/app/(product)/admin/page"

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
    loadAdminAuditEvents: vi.fn(),
    searchAdminTenants: vi.fn(),
  }
})

const mockedLoadAuthSession = vi.mocked(loadAuthSession)
const mockedSearchAdminTenants = vi.mocked(searchAdminTenants)
const mockedLoadAdminAuditEvents = vi.mocked(loadAdminAuditEvents)
const mockedRedirect = vi.mocked(redirect)

beforeEach(() => {
  vi.clearAllMocks()
})

const tenantSummary = {
  id: "tenant-1",
  name: "示例租户",
  slug: "demo",
  status: "active",
  member_count: 2,
  created_at: "2026-07-01T08:00:00Z",
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
  return AdminPage({ searchParams: Promise.resolve(searchParams) })
}

test("renders the tenant table for a platform admin", async () => {
  // Given an authenticated platform admin and a tenant page from the API
  stubSession(true)
  mockedSearchAdminTenants.mockResolvedValue({ kind: "ok", tenants: [tenantSummary], total: 1 })
  mockedLoadAdminAuditEvents.mockResolvedValue({ kind: "ok", events: [] })

  // When the admin console renders
  render(await renderPage())

  // Then the tenant row and audit section are visible
  expect(screen.getByRole("link", { name: "示例租户" })).toHaveAttribute(
    "href",
    "/admin/tenants/tenant-1",
  )
  expect(screen.getByText("共 1 个租户")).toBeInTheDocument()
  expect(screen.getByText("暂无审计事件")).toBeInTheDocument()
})

test("forwards the search params to the tenant search", async () => {
  // Given an authenticated platform admin
  stubSession(true)
  mockedSearchAdminTenants.mockResolvedValue({ kind: "ok", tenants: [], total: 0 })
  mockedLoadAdminAuditEvents.mockResolvedValue({ kind: "ok", events: [] })

  // When the console renders with a query and status filter
  render(await renderPage({ query: "示例", status: "suspended" }))

  // Then the filters reach the admin client
  expect(mockedSearchAdminTenants).toHaveBeenCalledWith(expect.anything(), "session-token", {
    query: "示例",
    status: "suspended",
  })
})

test("denies the console to a non-admin user without calling the admin API", async () => {
  // Given an authenticated tenant user without the platform admin flag
  stubSession(false)

  // When the admin console renders
  render(await renderPage())

  // Then the forbidden notice shows and no admin request is made
  expect(screen.getByText("你没有访问平台管理控制台的权限。")).toBeInTheDocument()
  expect(mockedSearchAdminTenants).not.toHaveBeenCalled()
})

test("redirects to security settings when the API demands MFA enrollment", async () => {
  // Given a platform admin whose session has not completed MFA setup
  stubSession(true)
  mockedSearchAdminTenants.mockResolvedValue({ kind: "mfaRequired" })
  mockedLoadAdminAuditEvents.mockResolvedValue({ kind: "mfaRequired" })
  mockedRedirect.mockImplementation(() => {
    throw new Error("NEXT_REDIRECT")
  })

  // When the console renders it redirects into the MFA setup flow
  await expect(renderPage()).rejects.toThrow("NEXT_REDIRECT")
  expect(mockedRedirect).toHaveBeenCalledWith("/settings/security")
})
