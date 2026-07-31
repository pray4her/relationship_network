import { z } from "zod"

export const billingErrorDetails = [
  "subscription_not_found",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const billingErrorSchema = z
  .object({
    detail: z.enum(billingErrorDetails),
  })
  .readonly()

export const billingMetricSchema = z.enum([
  "owners",
  "companies",
  "active_jobs",
  "searches",
  "matches",
  "reports",
])

export const billingStatusSchema = z.enum(["trialing", "active", "expired", "cancelled"])

export const metricBalanceSchema = z
  .object({
    metric: billingMetricSchema,
    limit: z.int(),
    used: z.int(),
    reserved: z.int(),
    remaining: z.int(),
  })
  .readonly()

export const billingPlanSchema = z
  .object({
    code: z.string(),
    name: z.string(),
    version: z.int(),
  })
  .readonly()

export const billingSummarySchema = z
  .object({
    plan: billingPlanSchema,
    status: billingStatusSchema,
    trial_ends_at: z.string().nullable(),
    current_period_start: z.string(),
    current_period_end: z.string(),
    metrics: z.array(metricBalanceSchema),
  })
  .readonly()

export type BillingMetric = z.infer<typeof billingMetricSchema>
export type BillingStatus = z.infer<typeof billingStatusSchema>
export type MetricBalance = z.infer<typeof metricBalanceSchema>
export type BillingPlan = z.infer<typeof billingPlanSchema>
export type BillingSummary = z.infer<typeof billingSummarySchema>
export type BillingErrorDetail = z.infer<typeof billingErrorSchema>["detail"]
