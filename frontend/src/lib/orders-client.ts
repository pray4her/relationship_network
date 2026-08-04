import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import { type SubscriptionView, subscriptionViewSchema } from "./billing-contract"
import {
  type OrderView,
  orderListSchema,
  ordersErrorSchema,
  orderViewSchema,
  type SubmitOrderInput,
} from "./orders-contract"

const apiUrlSchema = z.url()

export type OrdersTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface OrdersTransport {
  submitOrder(session: string, input: SubmitOrderInput): Promise<OrdersTransportResponse>
  listOrders(session: string): Promise<OrdersTransportResponse>
  cancelSubscription(session: string): Promise<OrdersTransportResponse>
}

export class OrdersTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "OrdersTransportError"
  }
}

class KyOrdersTransport implements OrdersTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  submitOrder(session: string, input: SubmitOrderInput): Promise<OrdersTransportResponse> {
    return this.#request("/billing/orders", { json: input, method: "POST", session })
  }

  listOrders(session: string): Promise<OrdersTransportResponse> {
    return this.#request("/billing/orders", { method: "GET", session })
  }

  cancelSubscription(session: string): Promise<OrdersTransportResponse> {
    return this.#request("/billing/subscription/cancel", { method: "POST", session })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST"
      readonly session: string
      readonly json?: unknown
    },
  ): Promise<OrdersTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl).toString(), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` },
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
        ...(options.json === undefined ? {} : { json: options.json }),
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new OrdersTransportError("orders endpoint unavailable")
      }
      throw error
    }
  }
}

export function createOrdersTransport(): OrdersTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyOrdersTransport(baseUrl)
}

export type OrdersAccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }
  | { readonly kind: "readOnly" }

export function readOrdersErrorDetail(body: unknown) {
  const parsed = ordersErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: OrdersTransportResponse): OrdersAccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    const detail = readOrdersErrorDetail(response.body)
    if (detail === "mfa_required") {
      return { kind: "mfaRequired" }
    }
    if (detail === "subscription_read_only") {
      return { kind: "readOnly" }
    }
    return { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof OrdersTransportError || error instanceof ZodError
}

export type SubmitOrderResult =
  | { readonly kind: "ok"; readonly order: OrderView }
  | OrdersAccessFailure
  | { readonly kind: "notFound" }
  | { readonly kind: "conflict" }
  | { readonly kind: "unreachable" }

export async function submitOrder(
  transport: OrdersTransport,
  session: string,
  input: SubmitOrderInput,
): Promise<SubmitOrderResult> {
  try {
    const response = await transport.submitOrder(session, input)
    if (response.status === 200 || response.status === 201) {
      return { kind: "ok", order: orderViewSchema.parse(response.body) }
    }
    if (response.status === 404 && readOrdersErrorDetail(response.body) === "plan_not_found") {
      return { kind: "notFound" }
    }
    if (
      response.status === 409 &&
      readOrdersErrorDetail(response.body) === "idempotency_key_mismatch"
    ) {
      return { kind: "conflict" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type OrderListResult =
  | { readonly kind: "ok"; readonly orders: readonly OrderView[] }
  | OrdersAccessFailure
  | { readonly kind: "unreachable" }

export async function listOrders(
  transport: OrdersTransport,
  session: string,
): Promise<OrderListResult> {
  try {
    const response = await transport.listOrders(session)
    if (response.status === 200) {
      return { kind: "ok", orders: orderListSchema.parse(response.body).orders }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type CancelSubscriptionResult =
  | { readonly kind: "ok"; readonly subscription: SubscriptionView }
  | OrdersAccessFailure
  | { readonly kind: "notFound" }
  | { readonly kind: "unreachable" }

export async function cancelSubscription(
  transport: OrdersTransport,
  session: string,
): Promise<CancelSubscriptionResult> {
  try {
    const response = await transport.cancelSubscription(session)
    if (response.status === 200) {
      return { kind: "ok", subscription: subscriptionViewSchema.parse(response.body) }
    }
    if (
      response.status === 404 &&
      readOrdersErrorDetail(response.body) === "subscription_not_found"
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
