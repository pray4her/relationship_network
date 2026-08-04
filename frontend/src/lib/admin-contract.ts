import { z } from "zod"

export const adminErrorDetails = [
  "not_authenticated",
  "platform_admin_required",
  "mfa_required",
  "tenant_not_found",
  "order_not_found",
  "order_already_confirmed",
  "order_already_rejected",
] as const

export const adminErrorSchema = z
  .object({
    detail: z.enum(adminErrorDetails),
  })
  .readonly()

export const tenantStatusSchema = z.enum(["active", "suspended"])

export const adminTenantSummarySchema = z
  .object({
    id: z.string(),
    name: z.string(),
    slug: z.string(),
    status: tenantStatusSchema,
    member_count: z.number().int(),
    created_at: z.string(),
  })
  .readonly()

export const adminTenantListSchema = z
  .object({
    tenants: z.array(adminTenantSummarySchema),
    total: z.number().int(),
  })
  .readonly()

export const adminTenantDetailSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    slug: z.string(),
    status: tenantStatusSchema,
    mfa_required: z.boolean(),
    member_count: z.number().int(),
    created_at: z.string(),
  })
  .readonly()

export const adminAuditEventSchema = z
  .object({
    id: z.string(),
    actor_id: z.string(),
    action: z.string(),
    target_type: z.string(),
    target_id: z.string(),
    result: z.string(),
    detail: z.string(),
    created_at: z.string(),
  })
  .readonly()

export const adminAuditEventListSchema = z
  .object({
    events: z.array(adminAuditEventSchema),
  })
  .readonly()

export type AdminErrorDetail = z.infer<typeof adminErrorSchema>["detail"]
export type TenantStatus = z.infer<typeof tenantStatusSchema>
export type AdminTenantSummary = z.infer<typeof adminTenantSummarySchema>
export type AdminTenantList = z.infer<typeof adminTenantListSchema>
export type AdminTenantDetail = z.infer<typeof adminTenantDetailSchema>
export type AdminAuditEvent = z.infer<typeof adminAuditEventSchema>
