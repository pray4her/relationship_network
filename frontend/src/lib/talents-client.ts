import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type TalentsErrorDetail,
  type TalentView,
  talentsErrorSchema,
  talentViewSchema,
} from "./talents-contract"

const apiUrlSchema = z.url()

export type TalentsTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface TalentsTransport {
  get(session: string, talentId: string): Promise<TalentsTransportResponse>
}

export class TalentsTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "TalentsTransportError"
  }
}

class KyTalentsTransport implements TalentsTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  get(session: string, talentId: string): Promise<TalentsTransportResponse> {
    return this.#request(`/talents/${talentId}`, { method: "GET", session })
  }

  async #request(
    path: string,
    options: { readonly method: "GET"; readonly session: string },
  ): Promise<TalentsTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl).toString(), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` },
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new TalentsTransportError("talents endpoint unavailable")
      }
      throw error
    }
  }
}

export function createTalentsTransport(): TalentsTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyTalentsTransport(baseUrl)
}

export type AccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export function readTalentsErrorDetail(body: unknown): TalentsErrorDetail | null {
  const parsed = talentsErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: TalentsTransportResponse): AccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    const detail = readTalentsErrorDetail(response.body)
    if (detail === "mfa_required") {
      return { kind: "mfaRequired" }
    }
    return { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof TalentsTransportError || error instanceof ZodError
}

export type TalentDetailResult =
  | { readonly kind: "ok"; readonly talent: TalentView }
  | { readonly kind: "notFound" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadTalentDetail(
  transport: TalentsTransport,
  session: string,
  talentId: string,
): Promise<TalentDetailResult> {
  try {
    const response = await transport.get(session, talentId)
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    const denied = accessFailure(response)
    if (denied) {
      return denied
    }
    if (response.status !== 200) {
      return { kind: "unreachable" }
    }
    return { kind: "ok", talent: talentViewSchema.parse(response.body) }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
