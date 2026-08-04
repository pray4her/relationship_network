import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type CompaniesErrorDetail,
  type CompanyDocumentView,
  type CompanyEventView,
  type CompanyView,
  companiesErrorSchema,
  companyDocumentListSchema,
  companyDocumentSchema,
  companyEventListSchema,
  companyListSchema,
  companyViewSchema,
} from "./companies-contract"

const apiUrlSchema = z.url()

export type CompaniesTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface CompaniesTransport {
  list(session: string): Promise<CompaniesTransportResponse>
  get(session: string, companyId: string): Promise<CompaniesTransportResponse>
  create(
    session: string,
    body: { readonly name: string; readonly profile_text?: string },
  ): Promise<CompaniesTransportResponse>
  update(
    session: string,
    companyId: string,
    body: { readonly name?: string; readonly profile_text?: string },
  ): Promise<CompaniesTransportResponse>
  archive(session: string, companyId: string): Promise<CompaniesTransportResponse>
  listDocuments(session: string, companyId: string): Promise<CompaniesTransportResponse>
  uploadDocument(
    session: string,
    companyId: string,
    file: Blob,
    filename: string,
  ): Promise<CompaniesTransportResponse>
  listEvents(session: string, companyId: string): Promise<CompaniesTransportResponse>
}

export class CompaniesTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "CompaniesTransportError"
  }
}

class KyCompaniesTransport implements CompaniesTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  list(session: string): Promise<CompaniesTransportResponse> {
    return this.#request("/companies", { method: "GET", session })
  }

  get(session: string, companyId: string): Promise<CompaniesTransportResponse> {
    return this.#request(`/companies/${companyId}`, { method: "GET", session })
  }

  create(
    session: string,
    body: { readonly name: string; readonly profile_text?: string },
  ): Promise<CompaniesTransportResponse> {
    return this.#request("/companies", { method: "POST", session, json: body })
  }

  update(
    session: string,
    companyId: string,
    body: { readonly name?: string; readonly profile_text?: string },
  ): Promise<CompaniesTransportResponse> {
    return this.#request(`/companies/${companyId}`, { method: "PATCH", session, json: body })
  }

  archive(session: string, companyId: string): Promise<CompaniesTransportResponse> {
    return this.#request(`/companies/${companyId}/archive`, { method: "POST", session })
  }

  listDocuments(session: string, companyId: string): Promise<CompaniesTransportResponse> {
    return this.#request(`/companies/${companyId}/documents`, { method: "GET", session })
  }

  async uploadDocument(
    session: string,
    companyId: string,
    file: Blob,
    filename: string,
  ): Promise<CompaniesTransportResponse> {
    const form = new FormData()
    form.append("file", file, filename)
    try {
      const response = await ky(new URL(`/companies/${companyId}/documents`, this.#baseUrl).toString(), {
        body: form,
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${session}` },
        method: "POST",
        retry: 0,
        throwHttpErrors: false,
        timeout: 30_000,
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new CompaniesTransportError("companies endpoint unavailable")
      }
      throw error
    }
  }

  listEvents(session: string, companyId: string): Promise<CompaniesTransportResponse> {
    return this.#request(`/companies/${companyId}/events`, { method: "GET", session })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST" | "PATCH"
      readonly session: string
      readonly json?: unknown
    },
  ): Promise<CompaniesTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl).toString(), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` },
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
        ...(options.json === undefined ? {} : { json: options.json }),
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new CompaniesTransportError("companies endpoint unavailable")
      }
      throw error
    }
  }
}

export function createCompaniesTransport(): CompaniesTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyCompaniesTransport(baseUrl)
}

export type AccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }
  | { readonly kind: "readOnly" }

export function readCompaniesErrorDetail(body: unknown): CompaniesErrorDetail | null {
  const parsed = companiesErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: CompaniesTransportResponse): AccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    const detail = readCompaniesErrorDetail(response.body)
    if (detail === "mfa_required") {
      return { kind: "mfaRequired" }
    }
    if (detail === "subscription_read_only") {
      return { kind: "readOnly" }
    }
    return { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof CompaniesTransportError || error instanceof ZodError
}

export type CompaniesListResult =
  | { readonly kind: "ok"; readonly companies: readonly CompanyView[] }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadCompanies(
  transport: CompaniesTransport,
  session: string,
): Promise<CompaniesListResult> {
  try {
    const response = await transport.list(session)
    if (response.status === 200) {
      return { kind: "ok", companies: companyListSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type CompanyDetailResult =
  | {
      readonly kind: "ok"
      readonly company: CompanyView
      readonly documents: readonly CompanyDocumentView[]
      readonly events: readonly CompanyEventView[]
    }
  | { readonly kind: "notFound" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadCompanyDetail(
  transport: CompaniesTransport,
  session: string,
  companyId: string,
): Promise<CompanyDetailResult> {
  try {
    const [companyResponse, documentsResponse, eventsResponse] = await Promise.all([
      transport.get(session, companyId),
      transport.listDocuments(session, companyId),
      transport.listEvents(session, companyId),
    ])
    if (companyResponse.status === 404) {
      return { kind: "notFound" }
    }
    const denied = accessFailure(companyResponse)
    if (denied) {
      return denied
    }
    if (companyResponse.status !== 200) {
      return { kind: "unreachable" }
    }
    const documents =
      documentsResponse.status === 200
        ? companyDocumentListSchema.parse(documentsResponse.body)
        : []
    const events =
      eventsResponse.status === 200 ? companyEventListSchema.parse(eventsResponse.body) : []
    return {
      kind: "ok",
      company: companyViewSchema.parse(companyResponse.body),
      documents,
      events,
    }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type CompanyMutationResult =
  | { readonly kind: "ok"; readonly company: CompanyView }
  | { readonly kind: "notFound" }
  | { readonly kind: "archived" }
  | { readonly kind: "quotaExceeded" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function createCompany(
  transport: CompaniesTransport,
  session: string,
  body: { readonly name: string; readonly profile_text?: string },
): Promise<CompanyMutationResult> {
  try {
    const response = await transport.create(session, body)
    if (response.status === 201) {
      return { kind: "ok", company: companyViewSchema.parse(response.body) }
    }
    if (response.status === 409 && readCompaniesErrorDetail(response.body) === "company_quota_exceeded") {
      return { kind: "quotaExceeded" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function updateCompany(
  transport: CompaniesTransport,
  session: string,
  companyId: string,
  body: { readonly name?: string; readonly profile_text?: string },
): Promise<CompanyMutationResult> {
  try {
    const response = await transport.update(session, companyId, body)
    if (response.status === 200) {
      return { kind: "ok", company: companyViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409 && readCompaniesErrorDetail(response.body) === "company_archived") {
      return { kind: "archived" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function archiveCompany(
  transport: CompaniesTransport,
  session: string,
  companyId: string,
): Promise<CompanyMutationResult> {
  try {
    const response = await transport.archive(session, companyId)
    if (response.status === 200) {
      return { kind: "ok", company: companyViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type DocumentUploadResult =
  | { readonly kind: "ok"; readonly document: CompanyDocumentView }
  | { readonly kind: "notFound" }
  | { readonly kind: "archived" }
  | { readonly kind: "invalidDocument" }
  | { readonly kind: "tooLarge" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function uploadCompanyDocument(
  transport: CompaniesTransport,
  session: string,
  companyId: string,
  file: Blob,
  filename: string,
): Promise<DocumentUploadResult> {
  try {
    const response = await transport.uploadDocument(session, companyId, file, filename)
    if (response.status === 201) {
      return { kind: "ok", document: companyDocumentSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409) {
      return { kind: "archived" }
    }
    if (response.status === 400) {
      return { kind: "invalidDocument" }
    }
    if (response.status === 413) {
      return { kind: "tooLarge" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
