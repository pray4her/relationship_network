import { expect, test } from "vitest"

import {
  type BillingTransport,
  BillingTransportError,
  type BillingTransportResponse,
  loadBillingSummary,
} from "../src/lib/billing-client"

const summaryBody = {
  plan: { code: "trial", name: "试用套餐", version: 1 },
  status: "trialing",
  trial_ends_at: "2026-08-14T08:00:00+00:00",
  current_period_start: "2026-07-31T08:00:00+00:00",
  current_period_end: "2026-08-14T08:00:00+00:00",
  metrics: [
    { metric: "owners", limit: 1, used: 0, reserved: 0, remaining: 1 },
    { metric: "companies", limit: 1, used: 0, reserved: 0, remaining: 1 },
    { metric: "active_jobs", limit: 2, used: 0, reserved: 0, remaining: 2 },
    { metric: "searches", limit: 20, used: 0, reserved: 0, remaining: 20 },
    { metric: "matches", limit: 3, used: 0, reserved: 0, remaining: 3 },
    { metric: "reports", limit: 1, used: 0, reserved: 0, remaining: 1 },
  ],
} as const

class ScriptedBillingTransport implements BillingTransport {
  readonly #handler: () => Promise<BillingTransportResponse>

  constructor(handler: () => Promise<BillingTransportResponse>) {
    this.#handler = handler
  }

  loadSummary(): Promise<BillingTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: BillingTransportResponse): BillingTransport {
  return new ScriptedBillingTransport(() => Promise.resolve(response))
}

function failingTransport(): BillingTransport {
  return new ScriptedBillingTransport(() =>
    Promise.reject(new BillingTransportError("connection failed")),
  )
}

test("parses the billing summary on success", async () => {
  const result = await loadBillingSummary(fixedTransport({ body: summaryBody, status: 200 }), "s")

  expect(result).toEqual({ kind: "ok", summary: summaryBody })
})

test("maps an unauthenticated response to anonymous", async () => {
  await expect(
    loadBillingSummary(fixedTransport({ body: { detail: "not_authenticated" }, status: 401 }), "s"),
  ).resolves.toEqual({ kind: "anonymous" })
})

test("maps a permission failure to forbidden", async () => {
  await expect(
    loadBillingSummary(fixedTransport({ body: { detail: "permission_denied" }, status: 403 }), "s"),
  ).resolves.toEqual({ kind: "forbidden" })
  await expect(
    loadBillingSummary(
      fixedTransport({ body: { detail: "no_active_membership" }, status: 403 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "forbidden" })
})

test("maps an mfa requirement to mfaRequired", async () => {
  await expect(
    loadBillingSummary(fixedTransport({ body: { detail: "mfa_required" }, status: 403 }), "s"),
  ).resolves.toEqual({ kind: "mfaRequired" })
})

test("maps a missing subscription to notFound", async () => {
  await expect(
    loadBillingSummary(
      fixedTransport({ body: { detail: "subscription_not_found" }, status: 404 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "notFound" })
})

test("treats transport failures and out-of-contract bodies as unreachable", async () => {
  await expect(loadBillingSummary(failingTransport(), "s")).resolves.toEqual({
    kind: "unreachable",
  })

  const result = await loadBillingSummary(
    fixedTransport({ body: { nope: true }, status: 200 }),
    "s",
  )

  expect(result).toEqual({ kind: "unreachable" })
})
