"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  archiveCompany,
  createCompaniesTransport,
  createCompany,
  type CompanyMutationResult,
  type DocumentUploadResult,
  updateCompany,
  uploadCompanyDocument,
} from "@/lib/companies-client"
import { createCompanyInputSchema, updateCompanyInputSchema } from "@/lib/companies-contract"

export type CompanyFormState = {
  readonly fieldErrors: Readonly<Partial<Record<"name" | "profile_text", string>>>
  readonly formError: string | null
}

export type CompanyActionState = {
  readonly formError: string | null
}

const idleFormState: CompanyFormState = {
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

function mutationError(result: CompanyMutationResult | DocumentUploadResult): string {
  switch (result.kind) {
    case "quotaExceeded":
      return "企业数量已达套餐上限，请归档现有企业或升级套餐。可在用量页查看额度。"
    case "archived":
      return "企业已归档，不能再修改或上传文档"
    case "notFound":
      return "企业不存在或无权访问"
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

export async function createCompanyAction(
  _previous: CompanyFormState,
  formData: FormData,
): Promise<CompanyFormState> {
  const parsed = createCompanyInputSchema.safeParse({
    name: formString(formData, "name"),
    profile_text: formString(formData, "profile_text"),
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
  const result = await createCompany(createCompaniesTransport(), session, {
    name: parsed.data.name,
    profile_text: parsed.data.profile_text ?? "",
  })
  if (result.kind !== "ok") {
    return { fieldErrors: {}, formError: mutationError(result) }
  }
  revalidatePath("/companies")
  redirect(`/companies/${result.company.id}`)
}

export async function updateCompanyAction(
  _previous: CompanyFormState,
  formData: FormData,
): Promise<CompanyFormState> {
  const companyId = formString(formData, "company_id")
  const parsed = updateCompanyInputSchema.safeParse({
    name: formString(formData, "name"),
    profile_text: formString(formData, "profile_text"),
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
  const body: { name?: string; profile_text?: string } = {}
  if (parsed.data.name !== undefined) {
    body.name = parsed.data.name
  }
  if (parsed.data.profile_text !== undefined) {
    body.profile_text = parsed.data.profile_text
  }
  const result = await updateCompany(createCompaniesTransport(), session, companyId, body)
  if (result.kind !== "ok") {
    return { fieldErrors: {}, formError: mutationError(result) }
  }
  revalidatePath("/companies")
  revalidatePath(`/companies/${companyId}`)
  return idleFormState
}

export async function archiveCompanyAction(
  _previous: CompanyActionState,
  formData: FormData,
): Promise<CompanyActionState> {
  const companyId = formString(formData, "company_id")
  const session = await requireSession()
  const result = await archiveCompany(createCompaniesTransport(), session, companyId)
  if (result.kind !== "ok") {
    return { formError: mutationError(result) }
  }
  revalidatePath("/companies")
  revalidatePath(`/companies/${companyId}`)
  return { formError: null }
}

export async function uploadCompanyDocumentAction(
  _previous: CompanyActionState,
  formData: FormData,
): Promise<CompanyActionState> {
  const companyId = formString(formData, "company_id")
  const file = formData.get("file")
  if (!(file instanceof File) || file.size === 0) {
    return { formError: "请选择要上传的文件" }
  }
  const session = await requireSession()
  const result = await uploadCompanyDocument(
    createCompaniesTransport(),
    session,
    companyId,
    file,
    file.name,
  )
  if (result.kind !== "ok") {
    return { formError: mutationError(result) }
  }
  revalidatePath(`/companies/${companyId}`)
  return { formError: null }
}
