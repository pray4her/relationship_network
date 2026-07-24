"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  createMfaTransport,
  disableMfa,
  enableMfa,
  startMfaSetup,
  updateTenantMfaPolicy,
} from "@/lib/mfa-client"
import { mfaCodeInputSchema } from "@/lib/mfa-contract"

export type MfaSetupStartState = {
  readonly formError: string | null
  readonly setup: { readonly secret: string; readonly otpauthUrl: string } | null
}

export type MfaEnableFormState = {
  readonly fieldErrors: Readonly<Partial<Record<"code", string>>>
  readonly formError: string | null
  readonly recoveryCodes: readonly string[] | null
}

export type MfaDisableFormState = {
  readonly fieldErrors: Readonly<Partial<Record<"code", string>>>
  readonly formError: string | null
}

export type TenantMfaPolicyFormState = {
  readonly formError: string | null
  readonly notice: string | null
  readonly required: boolean | null
}

function formString(formData: FormData, field: string): string {
  const value = formData.get(field)
  return typeof value === "string" ? value : ""
}

async function requireSession(): Promise<string> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    redirect("/login")
  }
  return session
}

export async function startMfaSetupAction(
  _previous: MfaSetupStartState,
  _formData: FormData,
): Promise<MfaSetupStartState> {
  const session = await requireSession()
  const result = await startMfaSetup(createMfaTransport(), session)
  if (result.kind === "ok") {
    return {
      formError: null,
      setup: { otpauthUrl: result.otpauthUrl, secret: result.secret },
    }
  }
  if (result.kind === "alreadyEnabled") {
    return { formError: "两步验证已启用", setup: null }
  }
  if (result.kind === "anonymous") {
    return { formError: "登录已过期，请重新登录", setup: null }
  }
  return { formError: "服务暂时不可用，请稍后再试", setup: null }
}

export async function enableMfaAction(
  _previous: MfaEnableFormState,
  formData: FormData,
): Promise<MfaEnableFormState> {
  const parsed = mfaCodeInputSchema.safeParse({ code: formString(formData, "code").trim() })
  if (!parsed.success) {
    return {
      fieldErrors: { code: "请输入 6 位数字验证码" },
      formError: null,
      recoveryCodes: null,
    }
  }

  const session = await requireSession()
  const result = await enableMfa(createMfaTransport(), session, parsed.data.code)
  if (result.kind === "enabled") {
    revalidatePath("/settings/security")
    return { fieldErrors: {}, formError: null, recoveryCodes: result.recoveryCodes }
  }
  if (result.kind === "invalidCode") {
    return { fieldErrors: {}, formError: "验证码不正确", recoveryCodes: null }
  }
  if (result.kind === "notEnabled") {
    return { fieldErrors: {}, formError: "请先开始设置两步验证", recoveryCodes: null }
  }
  if (result.kind === "alreadyEnabled") {
    return { fieldErrors: {}, formError: "两步验证已启用", recoveryCodes: null }
  }
  if (result.kind === "anonymous") {
    return { fieldErrors: {}, formError: "登录已过期，请重新登录", recoveryCodes: null }
  }
  return { fieldErrors: {}, formError: "服务暂时不可用，请稍后再试", recoveryCodes: null }
}

export async function disableMfaAction(
  _previous: MfaDisableFormState,
  formData: FormData,
): Promise<MfaDisableFormState> {
  const parsed = mfaCodeInputSchema.safeParse({ code: formString(formData, "code").trim() })
  if (!parsed.success) {
    return { fieldErrors: { code: "请输入 6 位数字验证码" }, formError: null }
  }

  const session = await requireSession()
  const result = await disableMfa(createMfaTransport(), session, parsed.data.code)
  if (result.kind === "disabled") {
    revalidatePath("/settings/security")
    return { fieldErrors: {}, formError: null }
  }
  if (result.kind === "invalidCode") {
    return { fieldErrors: {}, formError: "验证码不正确" }
  }
  if (result.kind === "requiredByTenant") {
    return { fieldErrors: {}, formError: "租户已开启强制 MFA，无法停用" }
  }
  if (result.kind === "notEnabled") {
    return { fieldErrors: {}, formError: "两步验证尚未启用" }
  }
  if (result.kind === "anonymous") {
    return { fieldErrors: {}, formError: "登录已过期，请重新登录" }
  }
  return { fieldErrors: {}, formError: "服务暂时不可用，请稍后再试" }
}

export async function tenantMfaPolicyAction(
  _previous: TenantMfaPolicyFormState,
  formData: FormData,
): Promise<TenantMfaPolicyFormState> {
  const required = formString(formData, "required") === "true"
  const session = await requireSession()
  const result = await updateTenantMfaPolicy(createMfaTransport(), session, required)
  if (result.kind === "ok") {
    revalidatePath("/settings/security")
    return {
      formError: null,
      notice: result.policy.mfa_required ? "已开启强制 MFA" : "已关闭强制 MFA",
      required: result.policy.mfa_required,
    }
  }
  if (result.kind === "setupRequired") {
    return { formError: "请先为自己启用 MFA，再开启强制策略", notice: null, required: null }
  }
  if (result.kind === "forbidden") {
    return { formError: "没有租户管理权限", notice: null, required: null }
  }
  if (result.kind === "anonymous") {
    return { formError: "登录已过期，请重新登录", notice: null, required: null }
  }
  return { formError: "服务暂时不可用，请稍后再试", notice: null, required: null }
}
