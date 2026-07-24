import { afterEach, expect, test, vi } from "vitest"

import {
  type AuthTransport,
  AuthTransportError,
  type AuthTransportResponse,
  createAuthTransport,
  DEFAULT_SESSION_MAX_AGE,
  loadAuthSession,
  loadCurrentTenant,
  loginAccount,
  parseSessionCookie,
  registerAccount,
  sessionCookieOptions,
} from "../src/lib/auth-client"

const authViewBody = {
  role: "owner",
  tenant: { id: "tenant-1", name: "示例租户", slug: "demo" },
  user: { id: "user-1", email: "owner@example.com", display_name: "张三" },
} as const

class ScriptedAuthTransport implements AuthTransport {
  readonly #handler: () => Promise<AuthTransportResponse>

  constructor(handler: () => Promise<AuthTransportResponse>) {
    this.#handler = handler
  }

  register(): Promise<AuthTransportResponse> {
    return this.#handler()
  }

  login(): Promise<AuthTransportResponse> {
    return this.#handler()
  }

  logout(): Promise<AuthTransportResponse> {
    return this.#handler()
  }

  me(): Promise<AuthTransportResponse> {
    return this.#handler()
  }

  currentTenant(): Promise<AuthTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: AuthTransportResponse): AuthTransport {
  return new ScriptedAuthTransport(() => Promise.resolve(response))
}

function failingTransport(): AuthTransport {
  return new ScriptedAuthTransport(() =>
    Promise.reject(new AuthTransportError("connection failed")),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test("registers a new account and carries the issued session cookie", async () => {
  // Given the API accepts the registration and issues a session cookie
  const transport = fixedTransport({
    body: authViewBody,
    session: { maxAge: 1_209_600, secure: false, value: "session-token" },
    status: 201,
  })

  // When the registration crosses the frontend boundary
  const result = await registerAccount(transport, {
    display_name: "张三",
    email: "owner@example.com",
    password: "super-secret",
    tenant_name: null,
  })

  // Then the caller receives the parsed view and the cookie to persist
  expect(result).toEqual({
    kind: "registered",
    session: { maxAge: 1_209_600, secure: false, value: "session-token" },
    view: authViewBody,
  })
})

test("maps a 409 conflict to a duplicate-email result", async () => {
  // Given the API rejects the registration because the email exists
  const transport = fixedTransport({
    body: { detail: "email_already_registered" },
    session: null,
    status: 409,
  })

  // When the registration crosses the frontend boundary
  const result = await registerAccount(transport, {
    display_name: "张三",
    email: "owner@example.com",
    password: "super-secret",
    tenant_name: null,
  })

  // Then the form can show the dedicated duplicate-email message
  expect(result).toEqual({ kind: "duplicate" })
})

test("maps wrong password and unknown email to one generic login failure", async () => {
  // Given the API answers 401 for both failure modes
  const transport = fixedTransport({
    body: { detail: "invalid_credentials" },
    session: null,
    status: 401,
  })

  // When the login crosses the frontend boundary
  const result = await loginAccount(transport, {
    email: "owner@example.com",
    password: "wrong-password",
  })

  // Then the UI receives a single indistinguishable failure kind
  expect(result).toEqual({ kind: "invalidCredentials" })
})

test("returns an unreachable result when the API cannot be connected", async () => {
  // Given the transport cannot reach the API
  const transport = failingTransport()

  // When a login is attempted
  const result = await loginAccount(transport, {
    email: "owner@example.com",
    password: "super-secret",
  })

  // Then the failure is represented as a stable renderable state
  expect(result).toEqual({ kind: "unreachable" })
})

test("treats an out-of-contract success body as unreachable", async () => {
  // Given the API returns a payload outside the documented schema
  const transport = fixedTransport({ body: { status: "unexpected" }, session: null, status: 200 })

  // When the session is resolved
  const result = await loadAuthSession(transport, "session-token")

  // Then invalid data is not trusted by the component tree
  expect(result).toEqual({ kind: "unreachable" })
})

test("exposes a renewed session cookie from the me endpoint", async () => {
  // Given the API slides the session and sets a renewed cookie
  const transport = fixedTransport({
    body: authViewBody,
    session: { maxAge: 1_209_600, secure: false, value: "renewed-token" },
    status: 200,
  })

  // When the session is resolved server-side
  const result = await loadAuthSession(transport, "old-token")

  // Then the middleware receives the renewed cookie to apply
  expect(result).toEqual({
    kind: "authenticated",
    renewedSession: { maxAge: 1_209_600, secure: false, value: "renewed-token" },
    view: authViewBody,
  })
})

test("maps a 401 from the me endpoint to an anonymous session", async () => {
  const transport = fixedTransport({
    body: { detail: "not_authenticated" },
    session: null,
    status: 401,
  })

  const result = await loadAuthSession(transport, "expired-token")

  expect(result).toEqual({ kind: "anonymous" })
})

test("maps tenant endpoint statuses to explicit results", async () => {
  const tenant = { id: "tenant-1", name: "示例租户", role: "owner", slug: "demo" }

  await expect(
    loadCurrentTenant(fixedTransport({ body: tenant, session: null, status: 200 }), "s"),
  ).resolves.toEqual({
    kind: "ok",
    tenant,
  })
  await expect(
    loadCurrentTenant(fixedTransport({ body: null, session: null, status: 403 }), "s"),
  ).resolves.toEqual({ kind: "forbidden" })
})

test("parses the rn_session cookie and its attributes from set-cookie headers", () => {
  const session = parseSessionCookie([
    "other=ignore; Path=/",
    "rn_session=abc123; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600; Secure",
  ])

  expect(session).toEqual({ maxAge: 1_209_600, secure: true, value: "abc123" })
})

test("forwards the secure attribute and max-age fallback into outgoing cookie options", () => {
  expect(sessionCookieOptions({ maxAge: 1_209_600, secure: true, value: "abc123" })).toEqual({
    httpOnly: true,
    maxAge: 1_209_600,
    path: "/",
    sameSite: "lax",
    secure: true,
  })
  expect(sessionCookieOptions({ maxAge: null, secure: false, value: "abc123" })).toEqual({
    httpOnly: true,
    maxAge: DEFAULT_SESSION_MAX_AGE,
    path: "/",
    sameSite: "lax",
    secure: false,
  })
})

test("ignores unrelated and cleared cookies when parsing set-cookie headers", () => {
  expect(parseSessionCookie(["other=ignore; Path=/"])).toBeNull()
  expect(parseSessionCookie(["rn_session=; Path=/; Max-Age=0"])).toBeNull()
})

test("extracts the session cookie from a real API response", async () => {
  // Given the API responds over HTTP with a renewed rn_session cookie
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      const headers = new Headers({ "content-type": "application/json" })
      headers.append(
        "set-cookie",
        "rn_session=renewed-token; Path=/; HttpOnly; Max-Age=1209600; Secure",
      )
      return new Response(JSON.stringify(authViewBody), { headers, status: 200 })
    }),
  )

  // When the real HTTP transport resolves the session
  const result = await loadAuthSession(createAuthTransport(), "old-token")

  // Then the renewed cookie survives the transport boundary with its secure attribute
  expect(result).toEqual({
    kind: "authenticated",
    renewedSession: { maxAge: 1_209_600, secure: true, value: "renewed-token" },
    view: authViewBody,
  })
})
