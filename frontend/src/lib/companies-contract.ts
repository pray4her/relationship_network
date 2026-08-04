import { z } from "zod"

export const companiesErrorDetails = [
  "company_not_found",
  "company_archived",
  "company_quota_exceeded",
  "invalid_document",
  "document_too_large",
  "object_storage_unavailable",
  "subscription_read_only",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const companiesErrorSchema = z
  .object({
    detail: z.enum(companiesErrorDetails),
  })
  .readonly()

export const companyStatusSchema = z.enum(["active", "archived"])

export const companyViewSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    profile_text: z.string(),
    status: companyStatusSchema,
    created_at: z.string(),
    updated_at: z.string(),
    archived_at: z.string().nullable(),
  })
  .readonly()

export const companyListSchema = z.array(companyViewSchema)

export const companyDocumentSchema = z
  .object({
    id: z.string(),
    company_id: z.string(),
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

export const companyDocumentListSchema = z.array(companyDocumentSchema)

export const companyEventSchema = z
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

export const companyEventListSchema = z.array(companyEventSchema)

export const createCompanyInputSchema = z.object({
  name: z.string().trim().min(1, "请输入企业名称").max(200, "企业名称过长"),
  profile_text: z.string().max(100_000, "企业简介过长").optional(),
})

export const updateCompanyInputSchema = z.object({
  name: z.string().trim().min(1, "请输入企业名称").max(200, "企业名称过长").optional(),
  profile_text: z.string().max(100_000, "企业简介过长").optional(),
})

export type CompanyView = z.infer<typeof companyViewSchema>
export type CompanyDocumentView = z.infer<typeof companyDocumentSchema>
export type CompanyEventView = z.infer<typeof companyEventSchema>
export type CompaniesErrorDetail = z.infer<typeof companiesErrorSchema>["detail"]
export type CompanyStatus = z.infer<typeof companyStatusSchema>
