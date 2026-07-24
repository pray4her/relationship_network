import { z } from "zod"

export const authErrorDetails = [
  "email_already_registered",
  "invalid_credentials",
  "not_authenticated",
  "no_active_membership",
  "permission_denied",
  "mfa_required",
  "invitation_invalid",
  "invitation_email_mismatch",
] as const

export const authErrorSchema = z
  .object({
    detail: z.enum(authErrorDetails),
  })
  .readonly()

export const membershipRoleSchema = z.enum(["owner", "member"])

const authUserSchema = z
  .object({
    display_name: z.string(),
    email: z.string(),
    id: z.string(),
  })
  .readonly()

const authTenantSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    slug: z.string(),
  })
  .readonly()

export const authViewSchema = z
  .object({
    role: membershipRoleSchema,
    tenant: authTenantSchema,
    user: authUserSchema,
  })
  .readonly()

export const meViewSchema = z
  .object({
    role: membershipRoleSchema,
    tenant: authTenantSchema,
    user: authUserSchema,
    permissions: z.array(z.string()),
  })
  .readonly()

export const loginMfaRequiredSchema = z
  .object({
    mfa_required: z.literal(true),
    mfa_token: z.string(),
    expires_at: z.string(),
  })
  .readonly()

export const currentTenantSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    role: membershipRoleSchema,
    slug: z.string(),
  })
  .readonly()

export const loginInputSchema = z.object({
  email: z.email("邮箱格式不正确"),
  password: z.string().min(1, "请输入密码"),
})

export const registerInputSchema = z.object({
  display_name: z.string().trim().min(1, "显示名称必填").max(50, "显示名称最多 50 个字符"),
  email: z.email("邮箱格式不正确"),
  password: z.string().min(8, "密码至少 8 位"),
  tenant_name: z.string().trim().nullable(),
  invite_token: z.string().nullable().optional(),
})

export type AuthErrorDetail = z.infer<typeof authErrorSchema>["detail"]
export type AuthView = z.infer<typeof authViewSchema>
export type MeView = z.infer<typeof meViewSchema>
export type CurrentTenant = z.infer<typeof currentTenantSchema>
export type LoginInput = z.infer<typeof loginInputSchema>
export type MembershipRole = z.infer<typeof membershipRoleSchema>
export type RegisterInput = z.infer<typeof registerInputSchema>
