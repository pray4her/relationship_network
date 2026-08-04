"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import {
  confirmAdminOrder,
  createAdminTransport,
  rejectAdminOrder,
  updateAdminTenantStatus,
} from "@/lib/admin-client"
import { SESSION_COOKIE_NAME } from "@/lib/auth-client"

export type TenantStatusActionState = {
  readonly formError: string | null
}

export type OrderReviewActionState = {
  readonly formError: string | null
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

export async function tenantStatusAction(
  _previous: TenantStatusActionState,
  formData: FormData,
): Promise<TenantStatusActionState> {
  const tenantId = formString(formData, "tenant_id")
  const intent = formString(formData, "intent")
  if (intent !== "suspend" && intent !== "reactivate") {
    return { formError: "未知操作" }
  }

  const session = await requireSession()
  const result = await updateAdminTenantStatus(
    createAdminTransport(),
    session,
    tenantId,
    intent === "suspend" ? "suspended" : "active",
  )
  revalidatePath("/admin")
  revalidatePath(`/admin/tenants/${tenantId}`)

  if (result.kind === "ok") {
    return { formError: null }
  }
  if (result.kind === "notFound") {
    return { formError: "租户不存在或已被删除" }
  }
  if (result.kind === "mfaRequired") {
    return { formError: "请先完成两步验证设置，再执行租户操作" }
  }
  if (result.kind === "anonymous") {
    return { formError: "登录已过期，请重新登录" }
  }
  if (result.kind === "forbidden") {
    return { formError: "没有执行该操作的权限" }
  }
  return { formError: "服务暂时不可用，请稍后再试" }
}

function orderReviewError(result: { readonly kind: string; readonly detail?: string }): string {
  if (result.kind === "notFound") {
    return "订单不存在或已被删除"
  }
  if (result.kind === "conflict") {
    return result.detail === "order_already_rejected"
      ? "该订单已被拒绝，无法再确认"
      : "该订单已确认，无法再拒绝"
  }
  if (result.kind === "mfaRequired") {
    return "请先完成两步验证设置，再执行订单审核"
  }
  if (result.kind === "anonymous") {
    return "登录已过期，请重新登录"
  }
  if (result.kind === "forbidden") {
    return "没有执行该操作的权限"
  }
  return "服务暂时不可用，请稍后再试"
}

export async function confirmOrderAction(
  _previous: OrderReviewActionState,
  formData: FormData,
): Promise<OrderReviewActionState> {
  const orderId = formString(formData, "order_id")
  if (orderId === "") {
    return { formError: "缺少订单标识" }
  }

  const session = await requireSession()
  const result = await confirmAdminOrder(createAdminTransport(), session, orderId)
  revalidatePath("/admin/orders")

  if (result.kind === "ok") {
    return { formError: null }
  }
  return { formError: orderReviewError(result) }
}

export async function rejectOrderAction(
  _previous: OrderReviewActionState,
  formData: FormData,
): Promise<OrderReviewActionState> {
  const orderId = formString(formData, "order_id")
  if (orderId === "") {
    return { formError: "缺少订单标识" }
  }

  const session = await requireSession()
  const reason = formString(formData, "reason").trim()
  const result = await rejectAdminOrder(
    createAdminTransport(),
    session,
    orderId,
    reason === "" ? null : reason,
  )
  revalidatePath("/admin/orders")

  if (result.kind === "ok") {
    return { formError: null }
  }
  return { formError: orderReviewError(result) }
}
