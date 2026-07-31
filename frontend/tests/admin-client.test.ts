import { expect, test } from "vitest"

import {
  type AdminTransport,
  AdminTransportError,
  type AdminTransportResponse,
  loadAdminAuditEvents,
  loadAdminTenant,
  searchAdminTenants,
  updateAdminTenantStatus,
} from "../src/lib/admin-client"

const tenantSummaryBody = {
  id: "tenant-1",
  name: "示例租户",
  slug: "demo",
  status: "active",
  member_count: 2,
  created_at: "2026-07-01T08:00:00Z",
} as const

const tenantDetailBody = {
  ...tenantSummaryBody,
  mfa_required: false,
} as const

const auditEventBody = {
  id: "event-1",
  actor_id: "user-1",
  action: "tenant.suspend",
  target_type: "tenant",
  target_id: "tenant-1",
  result: "ok",
  detail: "租户已暂停",
  created_at: "2026-07-24T10:25:00Z",
} as const

class ScriptedAdminTransport implements AdminTransport {
  readonly #handler: () => Promise<AdminTransportResponse>

  constructor(handler: () => Promise<AdminTransportResponse>) {
    this.#handler = handler
  }

  searchTenants(): Promise<AdminTransportResponse> {
    return this.#handler()
  }

  readTenant(): Promise<AdminTransportResponse> {
    return this.#handler()
  }

  updateTenantStatus(): Promise<AdminTransportResponse> {
    return this.#handler()
  }

  listAuditEvents(): Promise<AdminTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: AdminTransportResponse): AdminTransport {
  return new ScriptedAdminTransport(() => Promise.resolve(response))
}

function failingTransport(): AdminTransport {
  return new ScriptedAdminTransport(() =>
    Promise.reject(new AdminTransportError("connection failed")),
  )
}

test("parses a tenant search page into summaries and total", async () => {
  // Given the API returns a page of tenant summaries
  const transport = fixedTransport({
    body: { tenants: [tenantSummaryBody], total: 1 },
    status: 200,
  })

  // When the search crosses the frontend boundary
  const result = await searchAdminTenants(transport, "session-token", {
    query: "示例",
    status: null,
  })

  // Then the caller receives the parsed list and total
  expect(result).toEqual({ kind: "ok", tenants: [tenantSummaryBody], total: 1 })
})

test("maps admin endpoint statuses to explicit access failures", async () => {
  const search = { query: null, status: null }

  await expect(
    searchAdminTenants(
      fixedTransport({ body: { detail: "not_authenticated" }, status: 401 }),
      "s",
      search,
    ),
  ).resolves.toEqual({ kind: "anonymous" })
  await expect(
    searchAdminTenants(
      fixedTransport({ body: { detail: "platform_admin_required" }, status: 403 }),
      "s",
      search,
    ),
  ).resolves.toEqual({ kind: "forbidden" })
  await expect(
    searchAdminTenants(
      fixedTransport({ body: { detail: "mfa_required" }, status: 403 }),
      "s",
      search,
    ),
  ).resolves.toEqual({ kind: "mfaRequired" })
})

test("maps a missing tenant to notFound on read and status update", async () => {
  const notFound = fixedTransport({ body: { detail: "tenant_not_found" }, status: 404 })

  await expect(loadAdminTenant(notFound, "s", "tenant-404")).resolves.toEqual({
    kind: "notFound",
  })
  await expect(updateAdminTenantStatus(notFound, "s", "tenant-404", "suspended")).resolves.toEqual({
    kind: "notFound",
  })
})

test("parses a tenant detail and an updated tenant detail", async () => {
  await expect(
    loadAdminTenant(fixedTransport({ body: tenantDetailBody, status: 200 }), "s", "tenant-1"),
  ).resolves.toEqual({ kind: "ok", tenant: tenantDetailBody })
  await expect(
    updateAdminTenantStatus(
      fixedTransport({ body: { ...tenantDetailBody, status: "suspended" }, status: 200 }),
      "s",
      "tenant-1",
      "suspended",
    ),
  ).resolves.toEqual({ kind: "ok", tenant: { ...tenantDetailBody, status: "suspended" } })
})

test("parses the audit event list", async () => {
  const transport = fixedTransport({ body: { events: [auditEventBody] }, status: 200 })

  const result = await loadAdminAuditEvents(transport, "session-token")

  expect(result).toEqual({ kind: "ok", events: [auditEventBody] })
})

test("treats an out-of-contract success body as unreachable", async () => {
  const transport = fixedTransport({ body: { status: "unexpected" }, status: 200 })

  const result = await loadAdminTenant(transport, "session-token", "tenant-1")

  expect(result).toEqual({ kind: "unreachable" })
})

test("returns an unreachable result when the API cannot be connected", async () => {
  const transport = failingTransport()

  await expect(
    searchAdminTenants(transport, "session-token", { query: null, status: null }),
  ).resolves.toEqual({ kind: "unreachable" })
  await expect(loadAdminAuditEvents(transport, "session-token")).resolves.toEqual({
    kind: "unreachable",
  })
})
