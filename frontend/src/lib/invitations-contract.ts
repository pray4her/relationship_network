import { z } from "zod"

export const invitationsErrorDetails = [
  "email_already_member",
  "invitation_already_pending",
  "invitation_not_found",
  "invitation_already_accepted",
  "invitation_invalid",
  "invitation_email_mismatch",
  "already_in_tenant",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const invitationsErrorSchema = z
  .object({
    detail: z.enum(invitationsErrorDetails),
  })
  .readonly()

export const invitationStatusSchema = z.enum(["pending", "accepted", "revoked", "expired"])

export const invitationViewSchema = z
  .object({
    id: z.string(),
    email: z.string(),
    status: invitationStatusSchema,
    expires_at: z.string(),
    accepted_at: z.string().nullable(),
    revoked_at: z.string().nullable(),
    created_at: z.string(),
  })
  .readonly()

export const invitationListSchema = z.array(invitationViewSchema)

export const invitationCreateSchema = z
  .object({
    invitation: invitationViewSchema,
    token: z.string(),
    invite_url: z.string(),
  })
  .readonly()

export const invitationPreviewSchema = z
  .object({
    email: z.string(),
    tenant_name: z.string(),
    expires_at: z.string(),
  })
  .readonly()

export const invitationAcceptanceSchema = z
  .object({
    tenant_id: z.string(),
    tenant_name: z.string(),
    tenant_slug: z.string(),
    role: z.enum(["owner", "member"]),
  })
  .readonly()

export type InvitationView = z.infer<typeof invitationViewSchema>
export type InvitationStatus = z.infer<typeof invitationStatusSchema>
export type InvitationPreview = z.infer<typeof invitationPreviewSchema>
export type InvitationAcceptance = z.infer<typeof invitationAcceptanceSchema>
export type InvitationsErrorDetail = z.infer<typeof invitationsErrorSchema>["detail"]
