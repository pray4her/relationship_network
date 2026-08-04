import { expect, test } from "vitest"

import {
  type AdminTransport,
  AdminTransportError,
  type AdminTransportResponse,
  confirmAdminOrder,
  listAdminOrders,
  loadAdminAuditEvents,
  loadAdminTenant,
  rejectAdminOrder,
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

  listOrders(): Promise<AdminTransportResponse> {
    return this.#handler()
  }

  confirmOrder(): Promise<AdminTransportResponse> {
    return this.#handler()
  }

  rejectOrder(): Promise<AdminTransportResponse> {
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

const orderBody = {
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

test("parses the admin order list", async () => {
  const transport = fixedTransport({ body: { orders: [orderBody] }, status: 200 })

  const result = await listAdminOrders(transport, "session-token", "pending")

  expect(result).toEqual({ kind: "ok", orders: [orderBody] })
})

test("parses confirm and reject order responses", async () => {
  const confirmed = { ...orderBody, status: "confirmed" } as const

  await expect(
    confirmAdminOrder(fixedTransport({ body: confirmed, status: 200 }), "s", "order-1"),
  ).resolves.toEqual({ kind: "ok", order: confirmed })
  await expect(
    rejectAdminOrder(fixedTransport({ body: orderBody, status: 200 }), "s", "order-1", "凭证无效"),
  ).resolves.toEqual({ kind: "ok", order: orderBody })
})

test("maps order review conflicts and missing orders", async () => {
  await expect(
    confirmAdminOrder(
      fixedTransport({ body: { detail: "order_already_rejected" }, status: 409 }),
      "s",
      "order-1",
    ),
  ).resolves.toEqual({ detail: "order_already_rejected", kind: "conflict" })
  await expect(
    rejectAdminOrder(
      fixedTransport({ body: { detail: "order_already_confirmed" }, status: 409 }),
      "s",
      "order-1",
      null,
    ),
  ).resolves.toEqual({ detail: "order_already_confirmed", kind: "conflict" })
  await expect(
    confirmAdminOrder(
      fixedTransport({ body: { detail: "order_not_found" }, status: 404 }),
      "s",
      "order-404",
    ),
  ).resolves.toEqual({ kind: "notFound" })
})
