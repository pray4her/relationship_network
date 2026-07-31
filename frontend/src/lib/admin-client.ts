import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import {
  type AdminAuditEvent,
  type AdminTenantDetail,
  type AdminTenantSummary,
  adminAuditEventListSchema,
  adminErrorSchema,
  adminTenantDetailSchema,
  adminTenantListSchema,
  type TenantStatus,
} from "./admin-contract"
import { SESSION_COOKIE_NAME } from "./auth-client"

const apiUrlSchema = z.url()

export type AdminTenantSearch = {
  readonly query: string | null
  readonly status: TenantStatus | null
}

export type AdminTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface AdminTransport {
  searchTenants(session: string, search: AdminTenantSearch): Promise<AdminTransportResponse>
  readTenant(session: string, tenantId: string): Promise<AdminTransportResponse>
  updateTenantStatus(
    session: string,
    tenantId: string,
    status: TenantStatus,
  ): Promise<AdminTransportResponse>
  listAuditEvents(session: string): Promise<AdminTransportResponse>
}

export class AdminTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "AdminTransportError"
  }
}

class KyAdminTransport implements AdminTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  searchTenants(session: string, search: AdminTenantSearch): Promise<AdminTransportResponse> {
    const path = new URL("/admin/tenants", this.#baseUrl)
    if (search.query !== null && search.query !== "") {
      path.searchParams.set("query", search.query)
    }
    if (search.status !== null) {
      path.searchParams.set("status", search.status)
    }
    return this.#request(path.toString(), { method: "GET", session })
  }

  readTenant(session: string, tenantId: string): Promise<AdminTransportResponse> {
    return this.#request(`/admin/tenants/${tenantId}`, { method: "GET", session })
  }

  updateTenantStatus(
    session: string,
    tenantId: string,
    status: TenantStatus,
  ): Promise<AdminTransportResponse> {
    return this.#request(`/admin/tenants/${tenantId}/status`, {
      json: { status },
      method: "POST",
      session,
    })
  }

  listAuditEvents(session: string): Promise<AdminTransportResponse> {
    return this.#request("/admin/audit-events", { method: "GET", session })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST"
      readonly session: string
      readonly json?: unknown
    },
  ): Promise<AdminTransportResponse> {
    try {
      const url = path.startsWith("http") ? path : new URL(path, this.#baseUrl).toString()
      const response = await ky(url, {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` },
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
        ...(options.json === undefined ? {} : { json: options.json }),
      })
      const body = response.status === 204 ? null : await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new AdminTransportError("admin endpoint unavailable")
      }
      throw error
    }
  }
}

export function createAdminTransport(): AdminTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyAdminTransport(baseUrl)
}

export type AdminAccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export function readAdminErrorDetail(body: unknown) {
  const parsed = adminErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: AdminTransportResponse): AdminAccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    return readAdminErrorDetail(response.body) === "mfa_required"
      ? { kind: "mfaRequired" }
      : { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof AdminTransportError || error instanceof ZodError
}

export type AdminTenantSearchResult =
  | {
      readonly kind: "ok"
      readonly tenants: readonly AdminTenantSummary[]
      readonly total: number
    }
  | AdminAccessFailure
  | { readonly kind: "unreachable" }

export async function searchAdminTenants(
  transport: AdminTransport,
  session: string,
  search: AdminTenantSearch,
): Promise<AdminTenantSearchResult> {
  try {
    const response = await transport.searchTenants(session, search)
    if (response.status === 200) {
      const list = adminTenantListSchema.parse(response.body)
      return { kind: "ok", tenants: list.tenants, total: list.total }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type AdminTenantResult =
  | { readonly kind: "ok"; readonly tenant: AdminTenantDetail }
  | { readonly kind: "notFound" }
  | AdminAccessFailure
  | { readonly kind: "unreachable" }

function tenantFailure(response: AdminTransportResponse): AdminTenantResult | null {
  if (response.status === 404) {
    return { kind: "notFound" }
  }
  return accessFailure(response)
}

export async function loadAdminTenant(
  transport: AdminTransport,
  session: string,
  tenantId: string,
): Promise<AdminTenantResult> {
  try {
    const response = await transport.readTenant(session, tenantId)
    if (response.status === 200) {
      return { kind: "ok", tenant: adminTenantDetailSchema.parse(response.body) }
    }
    return tenantFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function updateAdminTenantStatus(
  transport: AdminTransport,
  session: string,
  tenantId: string,
  status: TenantStatus,
): Promise<AdminTenantResult> {
  try {
    const response = await transport.updateTenantStatus(session, tenantId, status)
    if (response.status === 200) {
      return { kind: "ok", tenant: adminTenantDetailSchema.parse(response.body) }
    }
    return tenantFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type AdminAuditEventsResult =
  | { readonly kind: "ok"; readonly events: readonly AdminAuditEvent[] }
  | AdminAccessFailure
  | { readonly kind: "unreachable" }

export async function loadAdminAuditEvents(
  transport: AdminTransport,
  session: string,
): Promise<AdminAuditEventsResult> {
  try {
    const response = await transport.listAuditEvents(session)
    if (response.status === 200) {
      return { kind: "ok", events: adminAuditEventListSchema.parse(response.body).events }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
