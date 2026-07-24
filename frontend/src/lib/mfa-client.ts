import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"
import { parseSessionCookie, SESSION_COOKIE_NAME, type SessionCookie } from "./auth-client"
import { type AuthView, authViewSchema } from "./auth-contract"
import {
  type MfaStatus,
  type MfaVerifyInput,
  mfaEnableSchema,
  mfaErrorSchema,
  mfaSetupSchema,
  mfaStatusSchema,
  type TenantMfaPolicy,
  tenantMfaPolicySchema,
} from "./mfa-contract"

const apiUrlSchema = z.url()

export type MfaTransportResponse = {
  readonly status: number
  readonly body: unknown
  readonly session: SessionCookie | null
}

export interface MfaTransport {
  setup(session: string): Promise<MfaTransportResponse>
  enable(session: string, code: string): Promise<MfaTransportResponse>
  disable(session: string, code: string): Promise<MfaTransportResponse>
  status(session: string): Promise<MfaTransportResponse>
  verify(input: MfaVerifyInput): Promise<MfaTransportResponse>
  updateTenantMfaPolicy(session: string, required: boolean): Promise<MfaTransportResponse>
}

export class MfaTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "MfaTransportError"
  }
}

class KyMfaTransport implements MfaTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  setup(session: string): Promise<MfaTransportResponse> {
    return this.#request("/auth/mfa/setup", { method: "POST", session })
  }

  enable(session: string, code: string): Promise<MfaTransportResponse> {
    return this.#request("/auth/mfa/enable", { json: { code }, method: "POST", session })
  }

  disable(session: string, code: string): Promise<MfaTransportResponse> {
    return this.#request("/auth/mfa/disable", { json: { code }, method: "POST", session })
  }

  status(session: string): Promise<MfaTransportResponse> {
    return this.#request("/auth/mfa/status", { method: "GET", session })
  }

  verify(input: MfaVerifyInput): Promise<MfaTransportResponse> {
    const json =
      "code" in input
        ? { mfa_token: input.mfaToken, code: input.code }
        : { mfa_token: input.mfaToken, recovery_code: input.recoveryCode }
    return this.#request("/auth/mfa/verify", { json, method: "POST" })
  }

  updateTenantMfaPolicy(session: string, required: boolean): Promise<MfaTransportResponse> {
    return this.#request("/tenants/current/mfa-policy", {
      json: { required },
      method: "PUT",
      session,
    })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST" | "PUT"
      readonly session?: string
      readonly json?: unknown
    },
  ): Promise<MfaTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl).toString(), {
        cache: "no-store",
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
        ...(options.session === undefined
          ? {}
          : { headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` } }),
        ...(options.json === undefined ? {} : { json: options.json }),
      })
      const session = parseSessionCookie(response.headers.getSetCookie())
      const body = response.status === 204 ? null : await response.json<unknown>().catch(() => null)
      return { body, session, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new MfaTransportError("mfa endpoint unavailable")
      }
      throw error
    }
  }
}

export function createMfaTransport(): MfaTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyMfaTransport(baseUrl)
}

function readErrorDetail(body: unknown) {
  const parsed = mfaErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof MfaTransportError || error instanceof ZodError
}

export type MfaSetupResult =
  | { readonly kind: "ok"; readonly secret: string; readonly otpauthUrl: string }
  | { readonly kind: "alreadyEnabled" }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function startMfaSetup(
  transport: MfaTransport,
  session: string,
): Promise<MfaSetupResult> {
  try {
    const response = await transport.setup(session)
    if (response.status === 200) {
      const parsed = mfaSetupSchema.parse(response.body)
      return { kind: "ok", otpauthUrl: parsed.otpauth_url, secret: parsed.secret }
    }
    if (response.status === 401) {
      return { kind: "anonymous" }
    }
    if (response.status === 409) {
      return readErrorDetail(response.body) === "mfa_already_enabled"
        ? { kind: "alreadyEnabled" }
        : { kind: "unreachable" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type MfaEnableResult =
  | { readonly kind: "enabled"; readonly recoveryCodes: readonly string[] }
  | { readonly kind: "invalidCode" }
  | { readonly kind: "notEnabled" }
  | { readonly kind: "alreadyEnabled" }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function enableMfa(
  transport: MfaTransport,
  session: string,
  code: string,
): Promise<MfaEnableResult> {
  try {
    const response = await transport.enable(session, code)
    if (response.status === 200) {
      const parsed = mfaEnableSchema.parse(response.body)
      return { kind: "enabled", recoveryCodes: parsed.recovery_codes }
    }
    if (response.status === 401) {
      return readErrorDetail(response.body) === "invalid_mfa_code"
        ? { kind: "invalidCode" }
        : { kind: "anonymous" }
    }
    if (response.status === 409) {
      const detail = readErrorDetail(response.body)
      if (detail === "mfa_not_enabled") {
        return { kind: "notEnabled" }
      }
      if (detail === "mfa_already_enabled") {
        return { kind: "alreadyEnabled" }
      }
      return { kind: "unreachable" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type MfaDisableResult =
  | { readonly kind: "disabled" }
  | { readonly kind: "invalidCode" }
  | { readonly kind: "notEnabled" }
  | { readonly kind: "requiredByTenant" }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function disableMfa(
  transport: MfaTransport,
  session: string,
  code: string,
): Promise<MfaDisableResult> {
  try {
    const response = await transport.disable(session, code)
    if (response.status === 204 || response.status === 200) {
      return { kind: "disabled" }
    }
    if (response.status === 401) {
      return readErrorDetail(response.body) === "invalid_mfa_code"
        ? { kind: "invalidCode" }
        : { kind: "anonymous" }
    }
    if (response.status === 409) {
      const detail = readErrorDetail(response.body)
      if (detail === "mfa_required_by_tenant") {
        return { kind: "requiredByTenant" }
      }
      if (detail === "mfa_not_enabled") {
        return { kind: "notEnabled" }
      }
      return { kind: "unreachable" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type MfaStatusResult =
  | { readonly kind: "ok"; readonly status: MfaStatus }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function loadMfaStatus(
  transport: MfaTransport,
  session: string,
): Promise<MfaStatusResult> {
  try {
    const response = await transport.status(session)
    if (response.status === 200) {
      return { kind: "ok", status: mfaStatusSchema.parse(response.body) }
    }
    if (response.status === 401) {
      return { kind: "anonymous" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type MfaVerifyResult =
  | {
      readonly kind: "authenticated"
      readonly view: AuthView
      readonly session: SessionCookie | null
    }
  | { readonly kind: "invalidCode" }
  | { readonly kind: "challengeInvalid" }
  | { readonly kind: "unreachable" }

export async function verifyMfaChallenge(
  transport: MfaTransport,
  input: MfaVerifyInput,
): Promise<MfaVerifyResult> {
  try {
    const response = await transport.verify(input)
    if (response.status === 200) {
      return {
        kind: "authenticated",
        session: response.session,
        view: authViewSchema.parse(response.body),
      }
    }
    if (response.status === 401) {
      const detail = readErrorDetail(response.body)
      if (detail === "invalid_mfa_code") {
        return { kind: "invalidCode" }
      }
      if (detail === "mfa_challenge_invalid") {
        return { kind: "challengeInvalid" }
      }
      return { kind: "unreachable" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type TenantMfaPolicyResult =
  | { readonly kind: "ok"; readonly policy: TenantMfaPolicy }
  | { readonly kind: "setupRequired" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function updateTenantMfaPolicy(
  transport: MfaTransport,
  session: string,
  required: boolean,
): Promise<TenantMfaPolicyResult> {
  try {
    const response = await transport.updateTenantMfaPolicy(session, required)
    if (response.status === 200) {
      return { kind: "ok", policy: tenantMfaPolicySchema.parse(response.body) }
    }
    if (response.status === 401) {
      return { kind: "anonymous" }
    }
    if (response.status === 403) {
      return { kind: "forbidden" }
    }
    if (response.status === 409) {
      return readErrorDetail(response.body) === "mfa_setup_required"
        ? { kind: "setupRequired" }
        : { kind: "unreachable" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
