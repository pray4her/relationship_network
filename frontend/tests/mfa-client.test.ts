import { expect, test } from "vitest"

import {
  disableMfa,
  enableMfa,
  loadMfaStatus,
  type MfaTransport,
  MfaTransportError,
  type MfaTransportResponse,
  startMfaSetup,
  updateTenantMfaPolicy,
  verifyMfaChallenge,
} from "../src/lib/mfa-client"

const authViewBody = {
  role: "owner",
  tenant: { id: "tenant-1", name: "示例租户", slug: "demo" },
  user: {
    id: "user-1",
    email: "owner@example.com",
    display_name: "张三",
    is_platform_admin: false,
  },
} as const

class ScriptedMfaTransport implements MfaTransport {
  readonly #handler: () => Promise<MfaTransportResponse>

  constructor(handler: () => Promise<MfaTransportResponse>) {
    this.#handler = handler
  }

  setup(): Promise<MfaTransportResponse> {
    return this.#handler()
  }

  enable(): Promise<MfaTransportResponse> {
    return this.#handler()
  }

  disable(): Promise<MfaTransportResponse> {
    return this.#handler()
  }

  status(): Promise<MfaTransportResponse> {
    return this.#handler()
  }

  verify(): Promise<MfaTransportResponse> {
    return this.#handler()
  }

  updateTenantMfaPolicy(): Promise<MfaTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: MfaTransportResponse): MfaTransport {
  return new ScriptedMfaTransport(() => Promise.resolve(response))
}

function failingTransport(): MfaTransport {
  return new ScriptedMfaTransport(() => Promise.reject(new MfaTransportError("connection failed")))
}

test("returns the setup secret and otpauth url", async () => {
  const result = await startMfaSetup(
    fixedTransport({
      body: { otpauth_url: "otpauth://totp/demo?secret=ABC", secret: "ABC" },
      session: null,
      status: 200,
    }),
    "s",
  )

  expect(result).toEqual({
    kind: "ok",
    otpauthUrl: "otpauth://totp/demo?secret=ABC",
    secret: "ABC",
  })
})

test("maps setup conflicts and missing authentication", async () => {
  await expect(
    startMfaSetup(
      fixedTransport({ body: { detail: "mfa_already_enabled" }, session: null, status: 409 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "alreadyEnabled" })
  await expect(
    startMfaSetup(
      fixedTransport({ body: { detail: "not_authenticated" }, session: null, status: 401 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "anonymous" })
})

test("returns the recovery codes on enable and maps an invalid code", async () => {
  await expect(
    enableMfa(
      fixedTransport({
        body: { recovery_codes: ["code-1", "code-2"] },
        session: null,
        status: 200,
      }),
      "s",
      "123456",
    ),
  ).resolves.toEqual({ kind: "enabled", recoveryCodes: ["code-1", "code-2"] })
  await expect(
    enableMfa(
      fixedTransport({ body: { detail: "invalid_mfa_code" }, session: null, status: 401 }),
      "s",
      "000000",
    ),
  ).resolves.toEqual({ kind: "invalidCode" })
})

test("maps disable outcomes including the tenant-enforced conflict", async () => {
  await expect(
    disableMfa(fixedTransport({ body: null, session: null, status: 204 }), "s", "123456"),
  ).resolves.toEqual({ kind: "disabled" })
  await expect(
    disableMfa(
      fixedTransport({ body: { detail: "mfa_required_by_tenant" }, session: null, status: 409 }),
      "s",
      "123456",
    ),
  ).resolves.toEqual({ kind: "requiredByTenant" })
})

test("parses the mfa status", async () => {
  const result = await loadMfaStatus(
    fixedTransport({
      body: { enabled: true, recovery_codes_remaining: 7 },
      session: null,
      status: 200,
    }),
    "s",
  )

  expect(result).toEqual({ kind: "ok", status: { enabled: true, recovery_codes_remaining: 7 } })
})

test("verifies a totp challenge and carries the issued session", async () => {
  const result = await verifyMfaChallenge(
    fixedTransport({
      body: authViewBody,
      session: { maxAge: 1_209_600, secure: false, value: "session-token" },
      status: 200,
    }),
    { code: "123456", mfaToken: "mfa-token" },
  )

  expect(result).toEqual({
    kind: "authenticated",
    session: { maxAge: 1_209_600, secure: false, value: "session-token" },
    view: authViewBody,
  })
})

test("maps challenge verification failures to dedicated kinds", async () => {
  await expect(
    verifyMfaChallenge(
      fixedTransport({ body: { detail: "invalid_mfa_code" }, session: null, status: 401 }),
      { code: "000000", mfaToken: "mfa-token" },
    ),
  ).resolves.toEqual({ kind: "invalidCode" })
  await expect(
    verifyMfaChallenge(
      fixedTransport({ body: { detail: "mfa_challenge_invalid" }, session: null, status: 401 }),
      { mfaToken: "mfa-token", recoveryCode: "rc-1" },
    ),
  ).resolves.toEqual({ kind: "challengeInvalid" })
})

test("maps the tenant policy update including the setup-required conflict", async () => {
  const policy = { id: "tenant-1", mfa_required: true, name: "示例租户", slug: "demo" }

  await expect(
    updateTenantMfaPolicy(fixedTransport({ body: policy, session: null, status: 200 }), "s", true),
  ).resolves.toEqual({ kind: "ok", policy })
  await expect(
    updateTenantMfaPolicy(
      fixedTransport({ body: { detail: "mfa_setup_required" }, session: null, status: 409 }),
      "s",
      true,
    ),
  ).resolves.toEqual({ kind: "setupRequired" })
  await expect(
    updateTenantMfaPolicy(
      fixedTransport({ body: { detail: "permission_denied" }, session: null, status: 403 }),
      "s",
      true,
    ),
  ).resolves.toEqual({ kind: "forbidden" })
})

test("reports unreachable when the transport fails", async () => {
  await expect(loadMfaStatus(failingTransport(), "s")).resolves.toEqual({ kind: "unreachable" })
})
