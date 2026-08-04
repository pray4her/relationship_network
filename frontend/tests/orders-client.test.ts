import { expect, test } from "vitest"

import {
  cancelSubscription,
  listOrders,
  type OrdersTransport,
  OrdersTransportError,
  type OrdersTransportResponse,
  submitOrder,
} from "../src/lib/orders-client"
import type { SubmitOrderInput } from "../src/lib/orders-contract"

const orderBody = {
  id: "order-1",
  tenant_id: "tenant-1",
  plan_code: "standard",
  plan_version: 1,
  amount_cents: 19900,
  payment_reference: "PAY-20260801-001",
  payment_channel: "offline",
  payer_note: "对公转账",
  status: "pending",
  idempotency_key: "9f1c2a40-9c0a-4d6f-9d4b-0f6b1d2a3c4e",
  submitted_by: "user-1",
  reviewed_by: null,
  reviewed_at: null,
  review_note: "",
  created_at: "2026-08-01T08:00:00+00:00",
} as const

const submitInput: SubmitOrderInput = {
  amount_cents: 19900,
  idempotency_key: "9f1c2a40-9c0a-4d6f-9d4b-0f6b1d2a3c4e",
  payment_reference: "PAY-20260801-001",
  payer_note: "对公转账",
  plan_code: "standard",
}

type Handlers = {
  readonly cancelSubscription?: () => Promise<OrdersTransportResponse>
  readonly listOrders?: () => Promise<OrdersTransportResponse>
  readonly submitOrder?: () => Promise<OrdersTransportResponse>
}

class ScriptedOrdersTransport implements OrdersTransport {
  readonly #handlers: Handlers

  constructor(handlers: Handlers) {
    this.#handlers = handlers
  }

  submitOrder(): Promise<OrdersTransportResponse> {
    return this.#handlers.submitOrder?.() ?? Promise.reject(new Error("unexpected submitOrder"))
  }

  listOrders(): Promise<OrdersTransportResponse> {
    return this.#handlers.listOrders?.() ?? Promise.reject(new Error("unexpected listOrders"))
  }

  cancelSubscription(): Promise<OrdersTransportResponse> {
    return (
      this.#handlers.cancelSubscription?.() ??
      Promise.reject(new Error("unexpected cancelSubscription"))
    )
  }
}

function fixedTransport(
  method: keyof Handlers,
  response: OrdersTransportResponse,
): OrdersTransport {
  return new ScriptedOrdersTransport({ [method]: () => Promise.resolve(response) })
}

function failingTransport(method: keyof Handlers): OrdersTransport {
  return new ScriptedOrdersTransport({
    [method]: () => Promise.reject(new OrdersTransportError("connection failed")),
  })
}

test("lists orders on success", async () => {
  const result = await listOrders(
    fixedTransport("listOrders", { body: { orders: [orderBody] }, status: 200 }),
    "s",
  )

  expect(result).toEqual({ kind: "ok", orders: [orderBody] })
})

test("maps list access failures", async () => {
  await expect(
    listOrders(
      fixedTransport("listOrders", { body: { detail: "not_authenticated" }, status: 401 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "anonymous" })
  await expect(
    listOrders(
      fixedTransport("listOrders", { body: { detail: "permission_denied" }, status: 403 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "forbidden" })
  await expect(
    listOrders(
      fixedTransport("listOrders", { body: { detail: "mfa_required" }, status: 403 }),
      "s",
    ),
  ).resolves.toEqual({ kind: "mfaRequired" })
})

test("submits an order on success", async () => {
  const result = await submitOrder(
    fixedTransport("submitOrder", { body: orderBody, status: 201 }),
    "s",
    submitInput,
  )

  expect(result).toEqual({ kind: "ok", order: orderBody })
})

test("maps a read-only subscription on submit", async () => {
  await expect(
    submitOrder(
      fixedTransport("submitOrder", { body: { detail: "subscription_read_only" }, status: 403 }),
      "s",
      submitInput,
    ),
  ).resolves.toEqual({ kind: "readOnly" })
})

test("maps a missing plan on submit to notFound", async () => {
  await expect(
    submitOrder(
      fixedTransport("submitOrder", { body: { detail: "plan_not_found" }, status: 404 }),
      "s",
      submitInput,
    ),
  ).resolves.toEqual({ kind: "notFound" })
})

test("maps an idempotency mismatch on submit to conflict", async () => {
  await expect(
    submitOrder(
      fixedTransport("submitOrder", {
        body: { detail: "idempotency_key_mismatch" },
        status: 409,
      }),
      "s",
      submitInput,
    ),
  ).resolves.toEqual({ kind: "conflict" })
})

test("cancels the subscription on success", async () => {
  const subscriptionBody = {
    status: "active",
    current_period_end: "2026-09-01T08:00:00+00:00",
    cancel_requested_at: "2026-08-04T08:00:00+00:00",
    offline_order_id: "order-1",
  }

  const result = await cancelSubscription(
    fixedTransport("cancelSubscription", { body: subscriptionBody, status: 200 }),
    "s",
  )

  expect(result).toEqual({ kind: "ok", subscription: subscriptionBody })
})

test("maps a missing subscription on cancel to notFound", async () => {
  await expect(
    cancelSubscription(
      fixedTransport("cancelSubscription", {
        body: { detail: "subscription_not_found" },
        status: 404,
      }),
      "s",
    ),
  ).resolves.toEqual({ kind: "notFound" })
})

test("treats transport failures and out-of-contract bodies as unreachable", async () => {
  await expect(listOrders(failingTransport("listOrders"), "s")).resolves.toEqual({
    kind: "unreachable",
  })
  await expect(submitOrder(failingTransport("submitOrder"), "s", submitInput)).resolves.toEqual({
    kind: "unreachable",
  })
  await expect(cancelSubscription(failingTransport("cancelSubscription"), "s")).resolves.toEqual({
    kind: "unreachable",
  })

  const result = await listOrders(
    fixedTransport("listOrders", { body: { nope: true }, status: 200 }),
    "s",
  )

  expect(result).toEqual({ kind: "unreachable" })
})
