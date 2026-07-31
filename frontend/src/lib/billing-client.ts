import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import { type BillingSummary, billingErrorSchema, billingSummarySchema } from "./billing-contract"

const apiUrlSchema = z.url()

export type BillingTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface BillingTransport {
  loadSummary(session: string): Promise<BillingTransportResponse>
}

export class BillingTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "BillingTransportError"
  }
}

class KyBillingTransport implements BillingTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  async loadSummary(session: string): Promise<BillingTransportResponse> {
    try {
      const response = await ky(new URL("/billing/summary", this.#baseUrl).toString(), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${session}` },
        method: "GET",
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new BillingTransportError("billing endpoint unavailable")
      }
      throw error
    }
  }
}

export function createBillingTransport(): BillingTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyBillingTransport(baseUrl)
}

export type AccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export function readBillingErrorDetail(body: unknown) {
  const parsed = billingErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: BillingTransportResponse): AccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    return readBillingErrorDetail(response.body) === "mfa_required"
      ? { kind: "mfaRequired" }
      : { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof BillingTransportError || error instanceof ZodError
}

export type BillingResult =
  | { readonly kind: "ok"; readonly summary: BillingSummary }
  | AccessFailure
  | { readonly kind: "notFound" }
  | { readonly kind: "unreachable" }

export async function loadBillingSummary(
  transport: BillingTransport,
  session: string,
): Promise<BillingResult> {
  try {
    const response = await transport.loadSummary(session)
    if (response.status === 200) {
      return { kind: "ok", summary: billingSummarySchema.parse(response.body) }
    }
    if (
      response.status === 404 &&
      readBillingErrorDetail(response.body) === "subscription_not_found"
    ) {
      return { kind: "notFound" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
