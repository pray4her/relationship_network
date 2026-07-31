"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { createAdminTransport, updateAdminTenantStatus } from "@/lib/admin-client"
import { SESSION_COOKIE_NAME } from "@/lib/auth-client"

export type TenantStatusActionState = {
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
