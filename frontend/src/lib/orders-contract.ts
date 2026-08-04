import { z } from "zod"

export const ordersErrorDetails = [
  "not_authenticated",
  "permission_denied",
  "no_active_membership",
  "mfa_required",
  "subscription_read_only",
  "plan_not_found",
  "order_not_found",
  "subscription_not_found",
  "order_already_confirmed",
  "order_already_rejected",
  "idempotency_key_mismatch",
] as const

export const ordersErrorSchema = z
  .object({
    detail: z.enum(ordersErrorDetails),
  })
  .readonly()

export const orderStatusSchema = z.enum(["pending", "confirmed", "rejected"])

export const orderViewSchema = z
  .object({
    id: z.string(),
    tenant_id: z.string(),
    plan_code: z.string(),
    plan_version: z.int(),
    amount_cents: z.int(),
    payment_reference: z.string(),
    payment_channel: z.string(),
    payer_note: z.string(),
    status: orderStatusSchema,
    idempotency_key: z.string(),
    submitted_by: z.string().nullable(),
    reviewed_by: z.string().nullable(),
    reviewed_at: z.string().nullable(),
    review_note: z.string(),
    created_at: z.string(),
  })
  .readonly()

export const orderListSchema = z
  .object({
    orders: z.array(orderViewSchema),
  })
  .readonly()

export const submitOrderInputSchema = z
  .object({
    plan_code: z.string().min(1),
    amount_cents: z.int().min(0),
    payment_reference: z.string().min(1),
    payer_note: z.string().optional(),
    idempotency_key: z.string().min(1),
  })
  .readonly()

export type OrderStatus = z.infer<typeof orderStatusSchema>
export type OrderView = z.infer<typeof orderViewSchema>
export type SubmitOrderInput = z.infer<typeof submitOrderInputSchema>
export type OrdersErrorDetail = z.infer<typeof ordersErrorSchema>["detail"]
