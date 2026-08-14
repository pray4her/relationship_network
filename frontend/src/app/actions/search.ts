"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createSearchTransport, submitSearchRun } from "@/lib/search-client"

export type SearchActionResult =
  | { readonly kind: "ok"; readonly runId: string }
  | { readonly kind: "error"; readonly message: string }

async function requireSession(): Promise<string> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) redirect("/login")
  return session
}

function submitError(detail: string): string {
  switch (detail) {
    case "invalid_utterance":
      return "搜索原句为空或超过 4000 个字符。"
    case "search_idempotency_fingerprint_conflict":
      return "同一幂等键对应了不同搜索内容，请刷新后重试。"
    case "search_creation_rate_limited":
      return "搜索过于频繁，请稍后再试。"
    case "search_in_progress":
      return "已有搜索正在执行，请稍后再试。"
    case "search_quota_exceeded":
      return "本计费周期搜索额度已用完。"
    default:
      return "搜索服务暂时不可用，请稍后再试。"
  }
}

function formString(formData: FormData, field: string): string {
  const value = formData.get(field)
  return typeof value === "string" ? value : ""
}

export async function submitSearchAction(formData: FormData): Promise<SearchActionResult> {
  const utterance = formString(formData, "utterance")
  const idempotencyKey = formString(formData, "idempotency_key")
  if (!utterance.trim()) {
    return { kind: "error", message: "请输入搜索原句。" }
  }
  if (utterance.length > 4000) {
    return { kind: "error", message: "搜索原句不能超过 4000 个字符。" }
  }
  if (!idempotencyKey) {
    return { kind: "error", message: "缺少幂等键，请重试。" }
  }
  const result = await submitSearchRun(
    createSearchTransport(),
    await requireSession(),
    utterance,
    idempotencyKey,
  )
  if (result.kind === "ok") return { kind: "ok", runId: result.run.id }
  if (result.kind === "anonymous") return { kind: "error", message: "登录已过期，请重新登录。" }
  if (result.kind === "forbidden") {
    return { kind: "error", message: "你没有发起搜索的权限，或租户已进入只读。" }
  }
  if (result.kind === "mfaRequired") return { kind: "error", message: "请先完成两步验证。" }
  if (result.kind === "error") return { kind: "error", message: submitError(result.detail) }
  return { kind: "error", message: "搜索服务暂时不可用，请稍后再试。" }
}
