"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  cancelLlmAttempt,
  copyLlmAttempt,
  createLlmAttempt,
  createLlmConfigurationTransport,
  type LlmMutationResult,
} from "@/lib/llm-configuration-client"
import {
  databaseUuidSchema,
  type LlmAttempt,
  llmCandidateSchema,
} from "@/lib/llm-configuration-contract"

export type LlmConfigurationActionResult =
  | { readonly attempt: LlmAttempt; readonly kind: "ok" }
  | {
      readonly fieldErrors: Readonly<Record<string, string>>
      readonly formError: string
      readonly kind: "error"
    }

const submissionSchema = llmCandidateSchema.extend({
  expected_current_version_id: databaseUuidSchema,
})

function formString(formData: FormData, field: string): string {
  const value = formData.get(field)
  return typeof value === "string" ? value : ""
}

function formNumber(formData: FormData, field: string): number {
  return Number(formString(formData, field))
}

async function requireSession(): Promise<string> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) redirect("/login")
  return session
}

function mutationError(result: Exclude<LlmMutationResult, { readonly kind: "ok" }>): string {
  if (result.kind === "conflict") {
    if (result.detail === "config_change_in_progress") return "已有配置变更正在执行，请等待或取消。"
    if (result.detail === "stale_current_configuration") return "当前配置已变化，请刷新后重新提交。"
    return "提示词与职位需求 Schema 不兼容，请选择已部署的兼容版本。"
  }
  if (result.kind === "mfaRequired") return "请先完成两步验证，再管理 LLM 配置。"
  if (result.kind === "forbidden") return "你没有管理平台 LLM 配置的权限。"
  if (result.kind === "anonymous") return "登录已过期，请重新登录。"
  if (result.kind === "notFound") return "目标配置版本或变更尝试不存在。"
  if (result.kind === "invalid") return "提交参数无效，请检查字段范围。"
  return "配置服务暂时不可用，请稍后重试。"
}

export async function submitLlmConfigurationAction(
  formData: FormData,
): Promise<LlmConfigurationActionResult> {
  const parsed = submissionSchema.safeParse({
    call_bindings: {
      job_requirement_parsing: {
        prompt_version_id: formString(formData, "parsing_prompt_version_id"),
        request_timeout_seconds: formNumber(formData, "parsing_request_timeout_seconds"),
      },
      search_interpretation: {
        prompt_version_id: formString(formData, "search_prompt_version_id"),
        request_timeout_seconds: formNumber(formData, "search_request_timeout_seconds"),
      },
    },
    expected_current_version_id: formString(formData, "expected_current_version_id"),
    max_output_tokens: formNumber(formData, "max_output_tokens"),
    model: formString(formData, "model"),
    temperature: formNumber(formData, "temperature"),
  })
  if (!parsed.success) {
    const fieldErrors: Record<string, string> = {}
    for (const issue of parsed.error.issues) {
      const field = issue.path.map(String).join(".") || "form"
      fieldErrors[field] ??= issue.message
    }
    return { fieldErrors, formError: "请修正标出的字段后重试。", kind: "error" }
  }
  const { expected_current_version_id: expectedId, ...candidate } = parsed.data
  const result = await createLlmAttempt(
    createLlmConfigurationTransport(),
    await requireSession(),
    candidate,
    expectedId,
  )
  if (result.kind !== "ok")
    return { fieldErrors: {}, formError: mutationError(result), kind: "error" }
  revalidatePath("/admin/llm-configuration")
  return result
}

export async function copyLlmConfigurationAction(
  versionId: string,
  expectedCurrentVersionId: string,
): Promise<LlmConfigurationActionResult> {
  const result = await copyLlmAttempt(
    createLlmConfigurationTransport(),
    await requireSession(),
    versionId,
    expectedCurrentVersionId,
  )
  if (result.kind !== "ok")
    return { fieldErrors: {}, formError: mutationError(result), kind: "error" }
  revalidatePath("/admin/llm-configuration")
  return result
}

export async function cancelLlmConfigurationAction(
  attemptId: string,
): Promise<LlmConfigurationActionResult> {
  const result = await cancelLlmAttempt(
    createLlmConfigurationTransport(),
    await requireSession(),
    attemptId,
  )
  if (result.kind !== "ok")
    return { fieldErrors: {}, formError: mutationError(result), kind: "error" }
  revalidatePath("/admin/llm-configuration")
  return result
}
