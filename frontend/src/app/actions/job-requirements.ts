"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  cancelRequirementTask,
  createRequirementTask,
  createRequirementTransport,
} from "@/lib/job-requirement-client"
import {
  cancelRequirementTaskInputSchema,
  createRequirementTaskInputSchema,
  type RequirementErrorDetail,
  type RequirementTask,
} from "@/lib/job-requirement-contract"

export type GenerateRequirementActionResult =
  | { readonly kind: "ok"; readonly task: RequirementTask }
  | {
      readonly kind: "error"
      readonly code: RequirementErrorDetail | "invalid_submission" | "unreachable"
      readonly message: string
    }

const errorMessages: Record<RequirementErrorDetail, string> = {
  job_not_found: "职位不存在或你无权访问。",
  job_archived: "职位已归档，只能查看已有结果。",
  requirement_source_not_found: "来源已变化，请刷新页面后重新选择。",
  requirement_material_unavailable: "所选材料尚未通过内容检查，请更换材料。",
  requirement_input_empty: "至少选择并填写一个非空来源。",
  requirement_material_correction_empty: "空材料必须先填写修正文案。",
  requirement_input_too_large: "输入超过字符上限，请取消部分材料或精简修正文案。",
  requirement_task_exists: "该职位已有生成任务，请先刷新查看状态。",
  requirement_draft_exists: "该职位已有可编辑草稿，当前不能生成替换草稿。",
  requirement_configuration_not_ready: "职位需求生成配置尚未就绪，请联系平台管理员启用 v2。",
  idempotency_conflict: "本次提交标识已用于不同内容。请修改来源后重新提交。",
  requirement_creation_rate_limited: "本小时新建任务已达上限，请稍后再试。",
  requirement_task_not_found: "职位需求解析任务不存在或你无权访问。",
  requirement_task_terminal: "任务已经结束，不能再取消。请刷新查看最新状态。",
  subscription_read_only: "订阅已过期，当前只能查看已有内容。",
  permission_denied: "你没有生成职位需求草稿的权限。",
  mfa_required: "租户要求两步验证，请先完成安全设置。",
  not_authenticated: "登录已过期，请重新登录。",
  no_active_membership: "当前账号没有可用的租户成员身份。",
}

export async function generateRequirementDraftAction(
  jobId: string,
  idempotencyKey: string,
  sources: readonly { readonly source_id: string; readonly corrected_text: string }[],
): Promise<GenerateRequirementActionResult> {
  const parsed = createRequirementTaskInputSchema.safeParse({ idempotencyKey, jobId, sources })
  if (!parsed.success) {
    return {
      kind: "error",
      code: "invalid_submission",
      message: "来源选择无效，请刷新页面后重试。",
    }
  }
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  const result = await createRequirementTask(
    createRequirementTransport(),
    session,
    parsed.data.jobId,
    parsed.data.idempotencyKey,
    parsed.data.sources,
  )
  if (result.kind === "ok") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return result
  }
  if (result.kind === "businessError") {
    return { kind: "error", code: result.detail, message: errorMessages[result.detail] }
  }
  if (result.kind === "anonymous") {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  if (result.kind === "mfaRequired") {
    return { kind: "error", code: "mfa_required", message: errorMessages.mfa_required }
  }
  if (result.kind === "readOnly") {
    return {
      kind: "error",
      code: "subscription_read_only",
      message: errorMessages.subscription_read_only,
    }
  }
  if (result.kind === "forbidden") {
    return { kind: "error", code: "permission_denied", message: errorMessages.permission_denied }
  }
  return { kind: "error", code: "unreachable", message: "服务暂时不可用，请稍后重试。" }
}

export async function cancelRequirementTaskAction(
  jobId: string,
  taskId: string,
): Promise<GenerateRequirementActionResult> {
  const parsed = cancelRequirementTaskInputSchema.safeParse({ jobId, taskId })
  if (!parsed.success) {
    return { kind: "error", code: "invalid_submission", message: "任务标识无效，请刷新页面。" }
  }
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  const result = await cancelRequirementTask(
    createRequirementTransport(),
    session,
    parsed.data.jobId,
    parsed.data.taskId,
  )
  if (result.kind === "ok") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return result
  }
  if (result.kind === "businessError") {
    return { kind: "error", code: result.detail, message: errorMessages[result.detail] }
  }
  if (result.kind === "anonymous") {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  if (result.kind === "mfaRequired") {
    return { kind: "error", code: "mfa_required", message: errorMessages.mfa_required }
  }
  if (result.kind === "readOnly") {
    return {
      kind: "error",
      code: "subscription_read_only",
      message: errorMessages.subscription_read_only,
    }
  }
  if (result.kind === "forbidden") {
    return { kind: "error", code: "permission_denied", message: errorMessages.permission_denied }
  }
  return { kind: "error", code: "unreachable", message: "服务暂时不可用，请稍后重试。" }
}
