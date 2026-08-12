import { z } from "zod"

export const jobsErrorDetails = [
  "job_not_found",
  "job_not_draft",
  "job_status_conflict",
  "job_quota_exceeded",
  "requirement_version_required",
  "company_not_found",
  "company_archived",
  "invalid_document",
  "document_too_large",
  "object_storage_unavailable",
  "subscription_read_only",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const jobsErrorSchema = z
  .object({
    detail: z.enum(jobsErrorDetails),
  })
  .readonly()

export const jobStatusSchema = z.enum(["draft", "active", "closed", "archived"])

export const jobViewSchema = z
  .object({
    id: z.string(),
    company_id: z.string(),
    title: z.string(),
    description: z.string(),
    status: jobStatusSchema,
    created_at: z.string(),
    updated_at: z.string(),
    archived_at: z.string().nullable(),
  })
  .readonly()

export const jobListSchema = z.array(jobViewSchema)

export const jobMaterialSchema = z
  .object({
    id: z.string(),
    job_id: z.string(),
    original_filename: z.string(),
    content_type: z.string(),
    byte_size: z.number().int().positive(),
    sha256: z.string(),
    extracted_text: z.string(),
    scan_status: z.string(),
    uploaded_by: z.string().nullable(),
    created_at: z.string(),
  })
  .readonly()

export const jobMaterialListSchema = z.array(jobMaterialSchema)

export const jobEventSchema = z
  .object({
    id: z.string(),
    actor_user_id: z.string().nullable(),
    action: z.string(),
    target_type: z.string(),
    target_id: z.string(),
    result: z.string(),
    detail: z.string(),
    created_at: z.string(),
  })
  .readonly()

export const jobEventListSchema = z.array(jobEventSchema)

export const createJobInputSchema = z.object({
  company_id: z.string().uuid("请选择所属企业"),
  title: z.string().trim().min(1, "请输入职位名称").max(200, "职位名称过长"),
  description: z.string().max(100_000, "职位描述过长").optional(),
})

export const updateJobInputSchema = z.object({
  title: z.string().trim().min(1, "请输入职位名称").max(200, "职位名称过长").optional(),
  description: z.string().max(100_000, "职位描述过长").optional(),
})

export type JobView = z.infer<typeof jobViewSchema>
export type JobMaterialView = z.infer<typeof jobMaterialSchema>
export type JobEventView = z.infer<typeof jobEventSchema>
export type JobsErrorDetail = z.infer<typeof jobsErrorSchema>["detail"]
export type JobStatus = z.infer<typeof jobStatusSchema>
