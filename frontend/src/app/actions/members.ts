"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  createInvitation,
  createInvitationsTransport,
  type InvitationAccessFailure,
  revokeInvitation,
} from "@/lib/invitations-client"
import {
  activateMember,
  assignMemberRoles,
  createMembersTransport,
  deactivateMember,
  type MemberMutationResult,
  type RemoveMemberResult,
  removeMember,
} from "@/lib/members-client"
import { inviteInputSchema } from "@/lib/members-contract"

export type InviteFormState = {
  readonly fieldErrors: Readonly<Partial<Record<"email", string>>>
  readonly formError: string | null
  readonly createdInvitation: { readonly inviteUrl: string; readonly token: string } | null
}

export type MemberActionState = {
  readonly formError: string | null
}

const idleInviteState: InviteFormState = {
  createdInvitation: null,
  fieldErrors: {},
  formError: null,
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

function accessError(failure: InvitationAccessFailure | { readonly kind: string }): string {
  if (failure.kind === "mfaRequired") {
    return "租户已启用强制 MFA，请先完成两步验证设置"
  }
  if (failure.kind === "anonymous") {
    return "登录已过期，请重新登录"
  }
  return "没有执行该操作的权限"
}

function mutationError(result: MemberMutationResult | RemoveMemberResult): string {
  switch (result.kind) {
    case "notFound":
      return "成员不存在或已被移除"
    case "protectedOwner":
      return "不能操作受保护的租户所有者"
    case "unreachable":
      return "服务暂时不可用，请稍后再试"
    default:
      return accessError(result)
  }
}

export async function inviteAction(
  _previous: InviteFormState,
  formData: FormData,
): Promise<InviteFormState> {
  const parsed = inviteInputSchema.safeParse({ email: formString(formData, "email") })
  if (!parsed.success) {
    return { ...idleInviteState, fieldErrors: { email: "邮箱格式不正确" } }
  }

  const session = await requireSession()
  const result = await createInvitation(createInvitationsTransport(), session, parsed.data.email)
  if (result.kind === "alreadyMember") {
    return { ...idleInviteState, formError: "该邮箱已是租户成员" }
  }
  if (result.kind === "alreadyPending") {
    return { ...idleInviteState, formError: "该邮箱已有待接受的邀请" }
  }
  if (result.kind === "unreachable") {
    return { ...idleInviteState, formError: "服务暂时不可用，请稍后再试" }
  }
  if (result.kind !== "created") {
    return { ...idleInviteState, formError: accessError(result) }
  }

  revalidatePath("/members")
  return {
    createdInvitation: { inviteUrl: result.inviteUrl, token: result.token },
    fieldErrors: {},
    formError: null,
  }
}

export async function revokeInvitationAction(
  _previous: MemberActionState,
  formData: FormData,
): Promise<MemberActionState> {
  const invitationId = formString(formData, "invitation_id")
  const session = await requireSession()
  const result = await revokeInvitation(createInvitationsTransport(), session, invitationId)
  revalidatePath("/members")
  if (result.kind === "revoked") {
    return { formError: null }
  }
  if (result.kind === "notFound") {
    return { formError: "邀请不存在或已被撤销" }
  }
  if (result.kind === "alreadyAccepted") {
    return { formError: "该邀请已被接受，无法撤销" }
  }
  if (result.kind === "unreachable") {
    return { formError: "服务暂时不可用，请稍后再试" }
  }
  return { formError: accessError(result) }
}

export async function memberStatusAction(
  _previous: MemberActionState,
  formData: FormData,
): Promise<MemberActionState> {
  const membershipId = formString(formData, "membership_id")
  const intent = formString(formData, "intent")
  const session = await requireSession()
  const transport = createMembersTransport()

  let result: MemberMutationResult | RemoveMemberResult
  if (intent === "deactivate") {
    result = await deactivateMember(transport, session, membershipId)
  } else if (intent === "activate") {
    result = await activateMember(transport, session, membershipId)
  } else if (intent === "remove") {
    result = await removeMember(transport, session, membershipId)
  } else {
    return { formError: "未知操作" }
  }

  revalidatePath("/members")
  if (result.kind === "ok" || result.kind === "removed") {
    return { formError: null }
  }
  return { formError: mutationError(result) }
}

export async function assignRolesAction(
  _previous: MemberActionState,
  formData: FormData,
): Promise<MemberActionState> {
  const membershipId = formString(formData, "membership_id")
  const roleIds = formData
    .getAll("role_ids")
    .filter((value): value is string => typeof value === "string")
  const session = await requireSession()
  const result = await assignMemberRoles(createMembersTransport(), session, membershipId, roleIds)
  revalidatePath("/members")
  if (result.kind === "ok") {
    return { formError: null }
  }
  return { formError: mutationError(result) }
}
