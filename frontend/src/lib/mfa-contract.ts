import { z } from "zod"

export const mfaErrorDetails = [
  "invalid_mfa_code",
  "mfa_already_enabled",
  "mfa_not_enabled",
  "mfa_required_by_tenant",
  "mfa_challenge_invalid",
  "mfa_setup_required",
  "tenant_not_found",
  "not_authenticated",
  "permission_denied",
] as const

export const mfaErrorSchema = z
  .object({
    detail: z.enum(mfaErrorDetails),
  })
  .readonly()

export const mfaSetupSchema = z
  .object({
    secret: z.string(),
    otpauth_url: z.string(),
  })
  .readonly()

export const mfaEnableSchema = z
  .object({
    recovery_codes: z.array(z.string()),
  })
  .readonly()

export const mfaStatusSchema = z
  .object({
    enabled: z.boolean(),
    recovery_codes_remaining: z.number(),
  })
  .readonly()

export const tenantMfaPolicySchema = z
  .object({
    id: z.string(),
    name: z.string(),
    slug: z.string(),
    mfa_required: z.boolean(),
  })
  .readonly()

export const mfaCodeInputSchema = z.object({
  code: z.string().regex(/^\d{6}$/, "请输入 6 位数字验证码"),
})

export type MfaSetup = z.infer<typeof mfaSetupSchema>
export type MfaStatus = z.infer<typeof mfaStatusSchema>
export type TenantMfaPolicy = z.infer<typeof tenantMfaPolicySchema>
export type MfaErrorDetail = z.infer<typeof mfaErrorSchema>["detail"]
export type MfaCodeInput = z.infer<typeof mfaCodeInputSchema>

export type MfaVerifyInput =
  | { readonly mfaToken: string; readonly code: string }
  | { readonly mfaToken: string; readonly recoveryCode: string }
