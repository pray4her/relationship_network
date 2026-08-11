import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type LlmCallDetail,
  type LlmCallList,
  type LlmCallMetadataStatus,
  type LlmCallOutcome,
  type LlmCallScope,
  type LlmCallType,
  type LlmRawResponse,
  llmCallDetailSchema,
  llmCallErrorSchema,
  llmCallListSchema,
  llmRawResponseSchema,
} from "./llm-call-contract"

const apiUrlSchema = z.url()

export type LlmCallFilters = {
  readonly callType?: LlmCallType
  readonly createdFrom?: string
  readonly createdTo?: string
  readonly cursor?: string
  readonly metadataStatus?: LlmCallMetadataStatus
  readonly outcome?: LlmCallOutcome
  readonly platformAttemptId?: string
  readonly scope?: LlmCallScope
  readonly tenantId?: string
}

export type LlmCallTransportResponse = { readonly body: unknown; readonly status: number }

export interface LlmCallTransport {
  detail(session: string, callId: string): Promise<LlmCallTransportResponse>
  list(session: string, filters: LlmCallFilters): Promise<LlmCallTransportResponse>
  rawResponse(session: string, callId: string): Promise<LlmCallTransportResponse>
}

export class LlmCallTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "LlmCallTransportError"
  }
}

class KyLlmCallTransport implements LlmCallTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  list(session: string, filters: LlmCallFilters): Promise<LlmCallTransportResponse> {
    const searchParams = toLlmCallSearchParams(filters)
    return this.#request(`/admin/llm-calls?${searchParams.toString()}`, "GET", session)
  }

  detail(session: string, callId: string): Promise<LlmCallTransportResponse> {
    return this.#request(`/admin/llm-calls/${callId}`, "GET", session)
  }

  rawResponse(session: string, callId: string): Promise<LlmCallTransportResponse> {
    return this.#request(`/admin/llm-calls/${callId}/raw-response`, "POST", session)
  }

  async #request(
    path: string,
    method: "GET" | "POST",
    session: string,
  ): Promise<LlmCallTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${session}` },
        method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
      })
      return { body: await response.json<unknown>().catch(() => null), status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new LlmCallTransportError("LLM call diagnostics endpoint unavailable")
      }
      throw error
    }
  }
}

export function toLlmCallSearchParams(filters: LlmCallFilters): URLSearchParams {
  const searchParams = new URLSearchParams()
  const entries: ReadonlyArray<readonly [string, string | undefined]> = [
    ["scope", filters.scope],
    ["call_type", filters.callType],
    ["outcome", filters.outcome],
    ["metadata_status", filters.metadataStatus],
    ["tenant_id", filters.tenantId],
    ["platform_attempt_id", filters.platformAttemptId],
    ["created_from", filters.createdFrom],
    ["created_to", filters.createdTo],
    ["cursor", filters.cursor],
  ]
  for (const [key, value] of entries) {
    if (value) searchParams.set(key, value)
  }
  return searchParams
}

export function createLlmCallTransport(): LlmCallTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyLlmCallTransport(baseUrl)
}

export type LlmCallAccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export type LlmCallListResult =
  | { readonly kind: "ok"; readonly page: LlmCallList }
  | LlmCallAccessFailure
  | { readonly kind: "unreachable" }

export type LlmCallDetailResult =
  | { readonly detail: LlmCallDetail; readonly kind: "ok" }
  | LlmCallAccessFailure
  | { readonly kind: "notFound" }
  | { readonly kind: "unreachable" }

export type LlmRawResponseResult =
  | { readonly kind: "ok"; readonly response: LlmRawResponse }
  | LlmCallAccessFailure
  | { readonly kind: "notFound" }
  | { readonly kind: "keyUnavailable" }
  | { readonly kind: "unreachable" }

function accessFailure(response: LlmCallTransportResponse): LlmCallAccessFailure | null {
  if (response.status === 401) return { kind: "anonymous" }
  if (response.status !== 403) return null
  const parsed = llmCallErrorSchema.safeParse(response.body)
  return parsed.success && parsed.data.detail === "mfa_required"
    ? { kind: "mfaRequired" }
    : { kind: "forbidden" }
}

function expectedFailure(error: unknown): boolean {
  return error instanceof LlmCallTransportError || error instanceof ZodError
}

export async function loadLlmCalls(
  transport: LlmCallTransport,
  session: string,
  filters: LlmCallFilters,
): Promise<LlmCallListResult> {
  try {
    const response = await transport.list(session, filters)
    if (response.status === 200) {
      return { kind: "ok", page: llmCallListSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}

export async function loadLlmCallDetail(
  transport: LlmCallTransport,
  session: string,
  callId: string,
): Promise<LlmCallDetailResult> {
  try {
    const response = await transport.detail(session, callId)
    if (response.status === 200) {
      return { detail: llmCallDetailSchema.parse(response.body), kind: "ok" }
    }
    const access = accessFailure(response)
    if (access) return access
    return response.status === 404 ? { kind: "notFound" } : { kind: "unreachable" }
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}

export async function revealLlmRawResponse(
  transport: LlmCallTransport,
  session: string,
  callId: string,
): Promise<LlmRawResponseResult> {
  try {
    const response = await transport.rawResponse(session, callId)
    if (response.status === 200) {
      return { kind: "ok", response: llmRawResponseSchema.parse(response.body) }
    }
    const access = accessFailure(response)
    if (access) return access
    if (response.status === 404) return { kind: "notFound" }
    if (response.status === 409) {
      const error = llmCallErrorSchema.safeParse(response.body)
      if (error.success && error.data.detail === "llm_raw_response_key_unavailable") {
        return { kind: "keyUnavailable" }
      }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}
