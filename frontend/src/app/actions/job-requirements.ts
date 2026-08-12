"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  abandonRequirementDraft,
  cancelRequirementTask,
  confirmRequirementDraft,
  copyCurrentRequirementVersion,
  createRequirementTask,
  createRequirementTransport,
  updateRequirementDraft,
} from "@/lib/job-requirement-client"
import {
  abandonRequirementDraftInputSchema,
  cancelRequirementTaskInputSchema,
  confirmRequirementDraftInputSchema,
  copyCurrentRequirementVersionInputSchema,
  createRequirementTaskInputSchema,
  type RequirementDraft,
  type RequirementErrorDetail,
  type RequirementTask,
  type RequirementVersion,
  updateRequirementDraftInputSchema,
} from "@/lib/job-requirement-contract"

export type GenerateRequirementActionResult =
  | { readonly kind: "ok"; readonly task: RequirementTask }
  | {
      readonly kind: "error"
      readonly code: RequirementErrorDetail | "invalid_submission" | "unreachable"
      readonly message: string
    }

export type RequirementDraftActionState =
  | { readonly kind: "idle" }
  | { readonly kind: "ok"; readonly draft: RequirementDraft; readonly message: string }
  | {
      readonly kind: "revisionConflict"
      readonly draft: RequirementDraft
      readonly message: string
    }
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
  requirement_draft_replacement_conflict: "草稿替换基线已变化，旧草稿保持不变。",
  requirement_draft_not_found: "职位需求草稿不存在或你无权访问。",
  requirement_draft_revision_conflict: "草稿已被其他成员更新，已加载最新修订。",
  requirement_draft_locked: "重新解析正在替换此草稿，任务结束前只能查看。",
  requirement_draft_not_editable: "该草稿已结束，不能继续修改。",
  requirement_draft_invalid: "草稿内容未通过完整校验，请检查标出的字段。",
  research_topic_query_empty: "研究主题查询不能为空，确认前请填写。",
  source_conflicts_unresolved: "仍有未解决的来源冲突，确认前请全部处理。",
  requirement_version_not_found: "当前没有可复制的职位需求版本。",
  requirement_editable_draft_exists: "已有可编辑草稿，请先完成或放弃后再复制。",
  requirement_version_required: "请先确认职位需求版本，再启用职位。",
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

export async function saveRequirementDraftAction(
  jobId: string,
  draftId: string,
  _previousState: RequirementDraftActionState,
  formData: FormData,
): Promise<RequirementDraftActionState> {
  const revisionRaw = formData.get("expected_revision")
  const resultRaw = formData.get("result")
  if (typeof revisionRaw !== "string" || typeof resultRaw !== "string") {
    return { kind: "error", code: "invalid_submission", message: "草稿提交内容不完整。" }
  }
  let result: unknown
  try {
    result = JSON.parse(resultRaw)
  } catch {
    return { kind: "error", code: "invalid_submission", message: "草稿提交格式无效。" }
  }
  const parsed = updateRequirementDraftInputSchema.safeParse({
    jobId,
    draftId,
    expectedRevision: Number(revisionRaw),
    result,
  })
  if (!parsed.success) {
    return { kind: "error", code: "invalid_submission", message: "请检查草稿中的必填内容。" }
  }
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  const response = await updateRequirementDraft(
    createRequirementTransport(),
    session,
    parsed.data.jobId,
    parsed.data.draftId,
    parsed.data.expectedRevision,
    parsed.data.result,
  )
  if (response.kind === "ok") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return { kind: "ok", draft: response.draft, message: "草稿已保存。" }
  }
  if (response.kind === "revisionConflict") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return {
      kind: "revisionConflict",
      draft: response.draft,
      message: errorMessages.requirement_draft_revision_conflict,
    }
  }
  return draftActionError(response)
}

export async function abandonRequirementDraftAction(
  jobId: string,
  draftId: string,
  expectedRevision: number,
): Promise<RequirementDraftActionState> {
  const parsed = abandonRequirementDraftInputSchema.safeParse({
    jobId,
    draftId,
    expectedRevision,
  })
  if (!parsed.success) {
    return { kind: "error", code: "invalid_submission", message: "草稿修订号无效。" }
  }
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  const response = await abandonRequirementDraft(
    createRequirementTransport(),
    session,
    parsed.data.jobId,
    parsed.data.draftId,
    parsed.data.expectedRevision,
  )
  if (response.kind === "ok") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return { kind: "ok", draft: response.draft, message: "草稿已放弃。" }
  }
  if (response.kind === "revisionConflict") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return {
      kind: "revisionConflict",
      draft: response.draft,
      message: errorMessages.requirement_draft_revision_conflict,
    }
  }
  return draftActionError(response)
}

export type ConfirmRequirementActionState =
  | { readonly kind: "idle" }
  | {
      readonly kind: "ok"
      readonly version: RequirementVersion
      readonly draft: RequirementDraft
      readonly message: string
    }
  | {
      readonly kind: "revisionConflict"
      readonly draft: RequirementDraft
      readonly message: string
    }
  | {
      readonly kind: "error"
      readonly code: RequirementErrorDetail | "invalid_submission" | "unreachable"
      readonly message: string
    }

export async function confirmRequirementDraftAction(
  jobId: string,
  draftId: string,
  expectedRevision: number,
): Promise<ConfirmRequirementActionState> {
  const parsed = confirmRequirementDraftInputSchema.safeParse({
    jobId,
    draftId,
    expectedRevision,
  })
  if (!parsed.success) {
    return { kind: "error", code: "invalid_submission", message: "草稿修订号无效。" }
  }
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  const response = await confirmRequirementDraft(
    createRequirementTransport(),
    session,
    parsed.data.jobId,
    parsed.data.draftId,
    parsed.data.expectedRevision,
  )
  if (response.kind === "ok") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return {
      kind: "ok",
      version: response.confirmed.version,
      draft: response.confirmed.draft,
      message: `已确认职位需求版本 v${response.confirmed.version.version_number}。`,
    }
  }
  if (response.kind === "revisionConflict") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return {
      kind: "revisionConflict",
      draft: response.draft,
      message: errorMessages.requirement_draft_revision_conflict,
    }
  }
  const errored = draftActionError(response)
  if (errored.kind === "error") {
    return errored
  }
  return { kind: "error", code: "unreachable", message: "服务暂时不可用，请稍后重试。" }
}

export async function copyCurrentRequirementVersionAction(
  jobId: string,
): Promise<RequirementDraftActionState> {
  const parsed = copyCurrentRequirementVersionInputSchema.safeParse({ jobId })
  if (!parsed.success) {
    return { kind: "error", code: "invalid_submission", message: "职位标识无效。" }
  }
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  const response = await copyCurrentRequirementVersion(
    createRequirementTransport(),
    session,
    parsed.data.jobId,
  )
  if (response.kind === "ok") {
    revalidatePath(`/jobs/${parsed.data.jobId}`)
    return { kind: "ok", draft: response.draft, message: "已复制当前版本为新草稿。" }
  }
  return draftActionError(response)
}

function draftActionError(
  response:
    | { readonly kind: "businessError"; readonly detail: RequirementErrorDetail }
    | { readonly kind: "anonymous" }
    | { readonly kind: "forbidden" }
    | { readonly kind: "mfaRequired" }
    | { readonly kind: "readOnly" }
    | { readonly kind: "unreachable" },
): RequirementDraftActionState {
  if (response.kind === "businessError") {
    return { kind: "error", code: response.detail, message: errorMessages[response.detail] }
  }
  if (response.kind === "anonymous") {
    return { kind: "error", code: "not_authenticated", message: errorMessages.not_authenticated }
  }
  if (response.kind === "mfaRequired") {
    return { kind: "error", code: "mfa_required", message: errorMessages.mfa_required }
  }
  if (response.kind === "readOnly") {
    return {
      kind: "error",
      code: "subscription_read_only",
      message: errorMessages.subscription_read_only,
    }
  }
  if (response.kind === "forbidden") {
    return { kind: "error", code: "permission_denied", message: errorMessages.permission_denied }
  }
  return { kind: "error", code: "unreachable", message: "服务暂时不可用，请稍后重试。" }
}
