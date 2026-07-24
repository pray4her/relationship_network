"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import type { ZodError } from "zod"

import {
  createAuthTransport,
  loginAccount,
  logoutAccount,
  MFA_CHALLENGE_COOKIE_NAME,
  MFA_CHALLENGE_MAX_AGE,
  registerAccount,
  SESSION_COOKIE_NAME,
  type SessionCookie,
  sessionCookieOptions,
} from "@/lib/auth-client"
import { loginInputSchema, registerInputSchema } from "@/lib/auth-contract"
import { createMfaTransport, verifyMfaChallenge } from "@/lib/mfa-client"

const authFormFields = ["email", "password", "display_name", "tenant_name"] as const

export type AuthFormField = (typeof authFormFields)[number]

export type AuthFormState = {
  readonly fieldErrors: Readonly<Partial<Record<AuthFormField, string>>>
  readonly formError: string | null
}

export type MfaVerifyFormState = {
  readonly fieldErrors: Readonly<Partial<Record<"code", string>>>
  readonly formError: string | null
}

function isAuthFormField(value: unknown): value is AuthFormField {
  return typeof value === "string" && (authFormFields as readonly string[]).includes(value)
}

function formString(formData: FormData, field: string): string {
  const value = formData.get(field)
  return typeof value === "string" ? value : ""
}

function validationState(error: ZodError): AuthFormState {
  const fieldErrors: Partial<Record<AuthFormField, string>> = {}
  for (const issue of error.issues) {
    const field = issue.path[0]
    if (isAuthFormField(field) && fieldErrors[field] === undefined) {
      fieldErrors[field] = issue.message
    }
  }
  return { fieldErrors, formError: null }
}

async function storeSessionCookie(session: SessionCookie | null): Promise<void> {
  if (!session) {
    return
  }
  const store = await cookies()
  store.set(SESSION_COOKIE_NAME, session.value, sessionCookieOptions(session))
}

export async function registerAction(
  _previous: AuthFormState,
  formData: FormData,
): Promise<AuthFormState> {
  const tenantName = formString(formData, "tenant_name").trim()
  const inviteToken = formString(formData, "invite_token").trim()
  const parsed = registerInputSchema.safeParse({
    display_name: formString(formData, "display_name"),
    email: formString(formData, "email"),
    password: formString(formData, "password"),
    tenant_name: tenantName === "" ? null : tenantName,
    invite_token: inviteToken === "" ? null : inviteToken,
  })
  if (!parsed.success) {
    return validationState(parsed.error)
  }

  const result = await registerAccount(createAuthTransport(), parsed.data)
  if (result.kind === "duplicate") {
    return { fieldErrors: { email: "该邮箱已注册，请直接登录" }, formError: null }
  }
  if (result.kind === "invitationInvalid") {
    return { fieldErrors: {}, formError: "邀请链接无效或已过期" }
  }
  if (result.kind === "invitationEmailMismatch") {
    return { fieldErrors: {}, formError: "注册邮箱必须与邀请邮箱一致" }
  }
  if (result.kind !== "registered") {
    return { fieldErrors: {}, formError: "服务暂时不可用，请稍后再试" }
  }

  await storeSessionCookie(result.session)
  redirect("/")
}

export async function loginAction(
  _previous: AuthFormState,
  formData: FormData,
): Promise<AuthFormState> {
  const parsed = loginInputSchema.safeParse({
    email: formString(formData, "email"),
    password: formString(formData, "password"),
  })
  if (!parsed.success) {
    return validationState(parsed.error)
  }

  const result = await loginAccount(createAuthTransport(), parsed.data)
  if (result.kind === "invalidCredentials") {
    return { fieldErrors: {}, formError: "邮箱或密码不正确" }
  }
  if (result.kind === "mfaRequired") {
    const store = await cookies()
    store.set(MFA_CHALLENGE_COOKIE_NAME, result.mfaToken, {
      httpOnly: true,
      maxAge: MFA_CHALLENGE_MAX_AGE,
      path: "/",
      sameSite: "lax",
      secure: process.env["NODE_ENV"] === "production",
    })
    redirect("/login/mfa")
  }
  if (result.kind !== "authenticated") {
    return { fieldErrors: {}, formError: "服务暂时不可用，请稍后再试" }
  }

  await storeSessionCookie(result.session)
  redirect("/")
}

export async function mfaVerifyAction(
  _previous: MfaVerifyFormState,
  formData: FormData,
): Promise<MfaVerifyFormState> {
  const store = await cookies()
  const mfaToken = store.get(MFA_CHALLENGE_COOKIE_NAME)?.value
  if (!mfaToken) {
    redirect("/login?error=mfa_challenge")
  }

  const factor = formString(formData, "factor") === "recovery_code" ? "recovery_code" : "code"
  const value = formString(formData, "code_value").trim()
  if (factor === "code" && !/^\d{6}$/.test(value)) {
    return { fieldErrors: { code: "请输入 6 位数字验证码" }, formError: null }
  }
  if (factor === "recovery_code" && value === "") {
    return { fieldErrors: { code: "请输入恢复码" }, formError: null }
  }

  const result = await verifyMfaChallenge(
    createMfaTransport(),
    factor === "code" ? { code: value, mfaToken } : { mfaToken, recoveryCode: value },
  )
  if (result.kind === "invalidCode") {
    return {
      fieldErrors: {},
      formError: factor === "code" ? "验证码不正确" : "恢复码不正确",
    }
  }
  if (result.kind === "challengeInvalid") {
    store.delete(MFA_CHALLENGE_COOKIE_NAME)
    redirect("/login?error=mfa_challenge")
  }
  if (result.kind !== "authenticated") {
    return { fieldErrors: {}, formError: "服务暂时不可用，请稍后再试" }
  }

  await storeSessionCookie(result.session)
  store.delete(MFA_CHALLENGE_COOKIE_NAME)
  redirect("/")
}

export async function logoutAction(): Promise<void> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (session) {
    await logoutAccount(createAuthTransport(), session)
  }
  store.delete(SESSION_COOKIE_NAME)
  redirect("/")
}
