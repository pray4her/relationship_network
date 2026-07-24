"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { acceptInvitation, createInvitationsTransport } from "@/lib/invitations-client"

export type AcceptInvitationFormState = {
  readonly formError: string | null
}

function formString(formData: FormData, field: string): string {
  const value = formData.get(field)
  return typeof value === "string" ? value : ""
}

export async function acceptInvitationAction(
  _previous: AcceptInvitationFormState,
  formData: FormData,
): Promise<AcceptInvitationFormState> {
  const token = formString(formData, "token")
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { formError: "请先登录后再接受邀请" }
  }

  const result = await acceptInvitation(createInvitationsTransport(), session, token)
  if (result.kind === "accepted") {
    redirect("/")
  }
  if (result.kind === "invalid") {
    return { formError: "邀请链接无效或已过期" }
  }
  if (result.kind === "emailMismatch") {
    return { formError: "当前账号邮箱与邀请邮箱不一致" }
  }
  if (result.kind === "alreadyInTenant") {
    return { formError: "当前账号已属于一个租户，无法接受邀请" }
  }
  if (result.kind === "anonymous") {
    return { formError: "登录已过期，请重新登录" }
  }
  return { formError: "服务暂时不可用，请稍后再试" }
}
