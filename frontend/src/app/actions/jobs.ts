"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  activateJob,
  archiveJob,
  closeJob,
  createJob,
  createJobsTransport,
  type JobMutationResult,
  type MaterialUploadResult,
  updateJob,
  uploadJobMaterial,
} from "@/lib/jobs-client"
import { createJobInputSchema, updateJobInputSchema } from "@/lib/jobs-contract"

export type JobFormState = {
  readonly fieldErrors: Readonly<Partial<Record<"company_id" | "title" | "description", string>>>
  readonly formError: string | null
}

export type JobActionState = {
  readonly formError: string | null
}

const idleFormState: JobFormState = {
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

function mutationError(result: JobMutationResult | MaterialUploadResult): string {
  switch (result.kind) {
    case "quotaExceeded":
      return "活跃职位数量已达套餐上限，请关闭现有职位或升级套餐。可在用量页查看额度。"
    case "notDraft":
      return "职位不在草稿状态，不能再编辑或上传材料"
    case "statusConflict":
      return "职位当前状态不允许该操作"
    case "companyArchived":
      return "所属企业已归档，不能再创建、启用职位或上传材料"
    case "notFound":
      return "职位不存在或无权访问"
    case "invalidDocument":
      return "仅支持 PDF、DOCX、TXT，且需通过内容校验"
    case "tooLarge":
      return "文件不能超过 10 MB"
    case "mfaRequired":
      return "租户已启用强制 MFA，请先完成两步验证设置"
    case "anonymous":
      return "登录已过期，请重新登录"
    case "readOnly":
      return "订阅已过期，当前为只读状态"
    case "forbidden":
      return "没有执行该操作的权限"
    case "unreachable":
      return "服务暂时不可用，请稍后再试"
    default:
      return "操作失败，请稍后再试"
  }
}

export async function createJobAction(
  _previous: JobFormState,
  formData: FormData,
): Promise<JobFormState> {
  const parsed = createJobInputSchema.safeParse({
    company_id: formString(formData, "company_id"),
    title: formString(formData, "title"),
    description: formString(formData, "description"),
  })
  if (!parsed.success) {
    const fieldErrors: Record<string, string> = {}
    for (const issue of parsed.error.issues) {
      const key = issue.path[0]
      if (typeof key === "string" && fieldErrors[key] === undefined) {
        fieldErrors[key] = issue.message
      }
    }
    return { fieldErrors, formError: null }
  }

  const session = await requireSession()
  const result = await createJob(createJobsTransport(), session, {
    company_id: parsed.data.company_id,
    title: parsed.data.title,
    description: parsed.data.description ?? "",
  })
  if (result.kind !== "ok") {
    return { fieldErrors: {}, formError: mutationError(result) }
  }
  revalidatePath("/jobs")
  redirect(`/jobs/${result.job.id}`)
}

export async function updateJobAction(
  _previous: JobFormState,
  formData: FormData,
): Promise<JobFormState> {
  const jobId = formString(formData, "job_id")
  const parsed = updateJobInputSchema.safeParse({
    title: formString(formData, "title"),
    description: formString(formData, "description"),
  })
  if (!parsed.success) {
    const fieldErrors: Record<string, string> = {}
    for (const issue of parsed.error.issues) {
      const key = issue.path[0]
      if (typeof key === "string" && fieldErrors[key] === undefined) {
        fieldErrors[key] = issue.message
      }
    }
    return { fieldErrors, formError: null }
  }

  const session = await requireSession()
  const body: { title?: string; description?: string } = {}
  if (parsed.data.title !== undefined) {
    body.title = parsed.data.title
  }
  if (parsed.data.description !== undefined) {
    body.description = parsed.data.description
  }
  const result = await updateJob(createJobsTransport(), session, jobId, body)
  if (result.kind !== "ok") {
    return { fieldErrors: {}, formError: mutationError(result) }
  }
  revalidatePath("/jobs")
  revalidatePath(`/jobs/${jobId}`)
  return idleFormState
}

export async function activateJobAction(
  _previous: JobActionState,
  formData: FormData,
): Promise<JobActionState> {
  const jobId = formString(formData, "job_id")
  const session = await requireSession()
  const result = await activateJob(createJobsTransport(), session, jobId)
  if (result.kind !== "ok") {
    return { formError: mutationError(result) }
  }
  revalidatePath("/jobs")
  revalidatePath(`/jobs/${jobId}`)
  return { formError: null }
}

export async function closeJobAction(
  _previous: JobActionState,
  formData: FormData,
): Promise<JobActionState> {
  const jobId = formString(formData, "job_id")
  const session = await requireSession()
  const result = await closeJob(createJobsTransport(), session, jobId)
  if (result.kind !== "ok") {
    return { formError: mutationError(result) }
  }
  revalidatePath("/jobs")
  revalidatePath(`/jobs/${jobId}`)
  return { formError: null }
}

export async function archiveJobAction(
  _previous: JobActionState,
  formData: FormData,
): Promise<JobActionState> {
  const jobId = formString(formData, "job_id")
  const session = await requireSession()
  const result = await archiveJob(createJobsTransport(), session, jobId)
  if (result.kind !== "ok") {
    return { formError: mutationError(result) }
  }
  revalidatePath("/jobs")
  revalidatePath(`/jobs/${jobId}`)
  return { formError: null }
}

export async function uploadJobMaterialAction(
  _previous: JobActionState,
  formData: FormData,
): Promise<JobActionState> {
  const jobId = formString(formData, "job_id")
  const file = formData.get("file")
  if (!(file instanceof File) || file.size === 0) {
    return { formError: "请选择要上传的文件" }
  }
  const session = await requireSession()
  const result = await uploadJobMaterial(createJobsTransport(), session, jobId, file, file.name)
  if (result.kind !== "ok") {
    return { formError: mutationError(result) }
  }
  revalidatePath(`/jobs/${jobId}`)
  return { formError: null }
}
