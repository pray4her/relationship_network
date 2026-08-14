import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type SearchErrorDetail,
  type SearchHitSnapshot,
  type SearchRunDetail,
  type SearchRunList,
  type SearchRunView,
  searchErrorSchema,
  searchRunDetailSchema,
  searchRunListSchema,
  searchRunViewSchema,
} from "./search-contract"

const apiUrlSchema = z.url()

export type SearchTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface SearchTransport {
  get(path: string, session: string): Promise<SearchTransportResponse>
  post(
    path: string,
    session: string,
    body: { readonly utterance: string; readonly idempotency_key: string },
  ): Promise<SearchTransportResponse>
}

export class SearchTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "SearchTransportError"
  }
}

class KySearchTransport implements SearchTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  get(path: string, session: string): Promise<SearchTransportResponse> {
    return this.#request(path, { method: "GET", session })
  }

  post(
    path: string,
    session: string,
    body: { readonly utterance: string; readonly idempotency_key: string },
  ): Promise<SearchTransportResponse> {
    return this.#request(path, { body, method: "POST", session })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST"
      readonly session: string
      readonly body?: { readonly utterance: string; readonly idempotency_key: string }
    },
  ): Promise<SearchTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl).toString(), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` },
        json: options.body,
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 60_000,
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new SearchTransportError("search endpoint unavailable")
      }
      throw error
    }
  }
}

export function createSearchTransport(): SearchTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KySearchTransport(baseUrl)
}

export type SearchAccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export function readSearchErrorDetail(body: unknown): SearchErrorDetail | null {
  const parsed = searchErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: SearchTransportResponse): SearchAccessFailure | null {
  if (response.status === 401) return { kind: "anonymous" }
  if (response.status === 403) {
    const detail = readSearchErrorDetail(response.body)
    if (detail === "mfa_required") return { kind: "mfaRequired" }
    return { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof SearchTransportError || error instanceof ZodError
}

export type SearchRunListResult =
  | { readonly kind: "ok"; readonly list: SearchRunList }
  | SearchAccessFailure
  | { readonly kind: "unreachable" }

export async function loadSearchRuns(
  transport: SearchTransport,
  session: string,
  cursor: string | null,
): Promise<SearchRunListResult> {
  try {
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""
    const response = await transport.get(`/search/runs${query}`, session)
    const denied = accessFailure(response)
    if (denied) return denied
    if (response.status !== 200) return { kind: "unreachable" }
    return { kind: "ok", list: searchRunListSchema.parse(response.body) }
  } catch (error) {
    if (isExpectedError(error)) return { kind: "unreachable" }
    throw error
  }
}

export type SearchRunDetailResult =
  | { readonly kind: "ok"; readonly detail: SearchRunDetail }
  | { readonly kind: "notFound" }
  | SearchAccessFailure
  | { readonly kind: "unreachable" }

export async function loadSearchRun(
  transport: SearchTransport,
  session: string,
  runId: string,
  sort: string | null,
  cursor: string | null,
): Promise<SearchRunDetailResult> {
  try {
    const params = new URLSearchParams()
    if (sort) params.set("sort", sort)
    if (cursor) params.set("cursor", cursor)
    const query = params.size > 0 ? `?${params.toString()}` : ""
    const response = await transport.get(`/search/runs/${runId}${query}`, session)
    if (response.status === 404) return { kind: "notFound" }
    const denied = accessFailure(response)
    if (denied) return denied
    if (response.status !== 200) return { kind: "unreachable" }
    return { kind: "ok", detail: searchRunDetailSchema.parse(response.body) }
  } catch (error) {
    if (isExpectedError(error)) return { kind: "unreachable" }
    throw error
  }
}

export type SearchSubmitResult =
  | { readonly kind: "ok"; readonly run: SearchRunView }
  | { readonly kind: "error"; readonly detail: SearchErrorDetail | "unknown" }
  | SearchAccessFailure
  | { readonly kind: "unreachable" }

export async function submitSearchRun(
  transport: SearchTransport,
  session: string,
  utterance: string,
  idempotencyKey: string,
): Promise<SearchSubmitResult> {
  try {
    const response = await transport.post("/search/runs", session, {
      idempotency_key: idempotencyKey,
      utterance,
    })
    const denied = accessFailure(response)
    if (denied) return denied
    if (response.status === 201) {
      return { kind: "ok", run: searchRunViewSchema.parse(response.body) }
    }
    const detail = readSearchErrorDetail(response.body)
    return { kind: "error", detail: detail ?? "unknown" }
  } catch (error) {
    if (isExpectedError(error)) return { kind: "unreachable" }
    throw error
  }
}

export type { SearchHitSnapshot }
