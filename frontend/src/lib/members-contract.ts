import { z } from "zod"

export const membersErrorDetails = [
  "membership_not_found",
  "role_not_found",
  "protected_owner",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const membersErrorSchema = z
  .object({
    detail: z.enum(membersErrorDetails),
  })
  .readonly()

export const memberViewSchema = z
  .object({
    membership_id: z.string(),
    user_id: z.string(),
    email: z.string(),
    display_name: z.string(),
    membership_role: z.enum(["owner", "member"]),
    is_active: z.boolean(),
    role_ids: z.array(z.string()),
  })
  .readonly()

export const memberListSchema = z.array(memberViewSchema)

export const roleViewSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    is_active: z.boolean(),
    permissions: z.array(z.string()),
  })
  .readonly()

export const roleListSchema = z.array(roleViewSchema)

export const inviteInputSchema = z.object({
  email: z.email("邮箱格式不正确"),
})

export type MemberView = z.infer<typeof memberViewSchema>
export type MembersErrorDetail = z.infer<typeof membersErrorSchema>["detail"]
export type RoleView = z.infer<typeof roleViewSchema>
export type InviteInput = z.infer<typeof inviteInputSchema>
