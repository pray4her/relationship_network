import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import {
  type AuthView,
  authErrorSchema,
  authViewSchema,
  type CurrentTenant,
  currentTenantSchema,
  type LoginInput,
  loginMfaRequiredSchema,
  type MeView,
  meViewSchema,
  type RegisterInput,
} from "./auth-contract"

const apiUrlSchema = z.url()

export const SESSION_COOKIE_NAME = "rn_session"
export const MFA_CHALLENGE_COOKIE_NAME = "rn_mfa_challenge"
export const MFA_CHALLENGE_MAX_AGE = 300
export const DEFAULT_SESSION_MAX_AGE = 1_209_600

export type SessionCookie = {
  readonly value: string
  readonly maxAge: number | null
  readonly secure: boolean
}

export type SessionCookieOptions = {
  readonly httpOnly: true
  readonly maxAge: number
  readonly path: "/"
  readonly sameSite: "lax"
  readonly secure: boolean
}

export function sessionCookieOptions(session: SessionCookie): SessionCookieOptions {
  return {
    httpOnly: true,
    maxAge: session.maxAge ?? DEFAULT_SESSION_MAX_AGE,
    path: "/",
    sameSite: "lax",
    secure: session.secure,
  }
}

export type AuthTransportResponse = {
  readonly status: number
  readonly body: unknown
  readonly session: SessionCookie | null
}

export interface AuthTransport {
  register(input: RegisterInput): Promise<AuthTransportResponse>
  login(input: LoginInput): Promise<AuthTransportResponse>
  logout(session: string): Promise<AuthTransportResponse>
  me(session: string): Promise<AuthTransportResponse>
  currentTenant(session: string): Promise<AuthTransportResponse>
}

export class AuthTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "AuthTransportError"
  }
}

export function parseSessionCookie(setCookies: readonly string[]): SessionCookie | null {
  for (const header of setCookies) {
    const parts = header.split(";")
    const first = parts[0]
    if (!first?.startsWith(`${SESSION_COOKIE_NAME}=`)) {
      continue
    }
    const value = first.slice(SESSION_COOKIE_NAME.length + 1).trim()
    if (value === "") {
      return null
    }
    let maxAge: number | null = null
    let secure = false
    for (const attribute of parts.slice(1)) {
      const [key = "", rawValue = ""] = attribute.split("=")
      const name = key.trim().toLowerCase()
      if (name === "max-age") {
        const parsed = Number.parseInt(rawValue.trim(), 10)
        maxAge = Number.isNaN(parsed) ? null : parsed
      }
      if (name === "secure") {
        secure = true
      }
    }
    return { maxAge, secure, value }
  }
  return null
}

class KyAuthTransport implements AuthTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  register(input: RegisterInput): Promise<AuthTransportResponse> {
    return this.#request("/auth/register", { json: input, method: "POST" })
  }

  login(input: LoginInput): Promise<AuthTransportResponse> {
    return this.#request("/auth/login", { json: input, method: "POST" })
  }

  logout(session: string): Promise<AuthTransportResponse> {
    return this.#request("/auth/logout", { method: "POST", session })
  }

  me(session: string): Promise<AuthTransportResponse> {
    return this.#request("/auth/me", { method: "GET", session })
  }

  currentTenant(session: string): Promise<AuthTransportResponse> {
    return this.#request("/tenants/current", { method: "GET", session })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST"
      readonly json?: unknown
      readonly session?: string
    },
  ): Promise<AuthTransportResponse> {
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
        throw new AuthTransportError("auth endpoint unavailable")
      }
      throw error
    }
  }
}

export function createAuthTransport(): AuthTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyAuthTransport(baseUrl)
}

export type RegisterResult =
  | {
      readonly kind: "registered"
      readonly view: AuthView
      readonly session: SessionCookie | null
    }
  | { readonly kind: "duplicate" }
  | { readonly kind: "invitationInvalid" }
  | { readonly kind: "invitationEmailMismatch" }
  | { readonly kind: "rejected" }
  | { readonly kind: "unreachable" }

export async function registerAccount(
  transport: AuthTransport,
  input: RegisterInput,
): Promise<RegisterResult> {
  try {
    const response = await transport.register(input)
    if (response.status === 201) {
      return {
        kind: "registered",
        session: response.session,
        view: authViewSchema.parse(response.body),
      }
    }
    if (response.status === 409) {
      const detail = readErrorDetail(response.body)
      return detail === "email_already_registered" ? { kind: "duplicate" } : { kind: "unreachable" }
    }
    if (response.status === 404) {
      const detail = readErrorDetail(response.body)
      return detail === "invitation_invalid"
        ? { kind: "invitationInvalid" }
        : { kind: "unreachable" }
    }
    if (response.status === 403) {
      const detail = readErrorDetail(response.body)
      return detail === "invitation_email_mismatch"
        ? { kind: "invitationEmailMismatch" }
        : { kind: "unreachable" }
    }
    if (response.status === 422) {
      return { kind: "rejected" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (error instanceof AuthTransportError || error instanceof ZodError) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type LoginResult =
  | {
      readonly kind: "authenticated"
      readonly view: AuthView
      readonly session: SessionCookie | null
    }
  | {
      readonly kind: "mfaRequired"
      readonly mfaToken: string
      readonly expiresAt: string
    }
  | { readonly kind: "invalidCredentials" }
  | { readonly kind: "unreachable" }

export async function loginAccount(
  transport: AuthTransport,
  input: LoginInput,
): Promise<LoginResult> {
  try {
    const response = await transport.login(input)
    if (response.status === 200) {
      const mfaRequired = loginMfaRequiredSchema.safeParse(response.body)
      if (mfaRequired.success) {
        return {
          kind: "mfaRequired",
          expiresAt: mfaRequired.data.expires_at,
          mfaToken: mfaRequired.data.mfa_token,
        }
      }
      return {
        kind: "authenticated",
        session: response.session,
        view: authViewSchema.parse(response.body),
      }
    }
    if (response.status === 401) {
      return { kind: "invalidCredentials" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (error instanceof AuthTransportError || error instanceof ZodError) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type AuthSessionResult =
  | {
      readonly kind: "authenticated"
      readonly view: MeView
      readonly renewedSession: SessionCookie | null
    }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function loadAuthSession(
  transport: AuthTransport,
  session: string,
): Promise<AuthSessionResult> {
  try {
    const response = await transport.me(session)
    if (response.status === 200) {
      return {
        kind: "authenticated",
        renewedSession: response.session,
        view: meViewSchema.parse(response.body),
      }
    }
    if (response.status === 401) {
      return { kind: "anonymous" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (error instanceof AuthTransportError || error instanceof ZodError) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type CurrentTenantResult =
  | { readonly kind: "ok"; readonly tenant: CurrentTenant }
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }
  | { readonly kind: "unreachable" }

export async function loadCurrentTenant(
  transport: AuthTransport,
  session: string,
): Promise<CurrentTenantResult> {
  try {
    const response = await transport.currentTenant(session)
    if (response.status === 200) {
      return { kind: "ok", tenant: currentTenantSchema.parse(response.body) }
    }
    if (response.status === 401) {
      return { kind: "anonymous" }
    }
    if (response.status === 403) {
      return readErrorDetail(response.body) === "mfa_required"
        ? { kind: "mfaRequired" }
        : { kind: "forbidden" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (error instanceof AuthTransportError || error instanceof ZodError) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function logoutAccount(transport: AuthTransport, session: string): Promise<void> {
  try {
    await transport.logout(session)
  } catch (error) {
    if (!(error instanceof AuthTransportError)) {
      throw error
    }
  }
}

function readErrorDetail(body: unknown) {
  const parsed = authErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}
