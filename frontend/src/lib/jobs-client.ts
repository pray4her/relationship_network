import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type JobEventView,
  type JobMaterialView,
  type JobStatus,
  type JobsErrorDetail,
  type JobView,
  jobEventListSchema,
  jobListSchema,
  jobMaterialListSchema,
  jobMaterialSchema,
  jobsErrorSchema,
  jobViewSchema,
} from "./jobs-contract"

const apiUrlSchema = z.url()

export type JobsTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface JobsTransport {
  list(
    session: string,
    filters: { readonly status?: JobStatus; readonly companyId?: string },
  ): Promise<JobsTransportResponse>
  get(session: string, jobId: string): Promise<JobsTransportResponse>
  create(
    session: string,
    body: {
      readonly company_id: string
      readonly title: string
      readonly description?: string
    },
  ): Promise<JobsTransportResponse>
  update(
    session: string,
    jobId: string,
    body: { readonly title?: string; readonly description?: string },
  ): Promise<JobsTransportResponse>
  activate(session: string, jobId: string): Promise<JobsTransportResponse>
  close(session: string, jobId: string): Promise<JobsTransportResponse>
  archive(session: string, jobId: string): Promise<JobsTransportResponse>
  listMaterials(session: string, jobId: string): Promise<JobsTransportResponse>
  uploadMaterial(
    session: string,
    jobId: string,
    file: Blob,
    filename: string,
  ): Promise<JobsTransportResponse>
  listEvents(session: string, jobId: string): Promise<JobsTransportResponse>
}

export class JobsTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "JobsTransportError"
  }
}

class KyJobsTransport implements JobsTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  list(
    session: string,
    filters: { readonly status?: JobStatus; readonly companyId?: string },
  ): Promise<JobsTransportResponse> {
    const params = new URLSearchParams()
    if (filters.status !== undefined) {
      params.set("status", filters.status)
    }
    if (filters.companyId !== undefined) {
      params.set("company_id", filters.companyId)
    }
    const query = params.toString()
    return this.#request(query ? `/jobs?${query}` : "/jobs", { method: "GET", session })
  }

  get(session: string, jobId: string): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}`, { method: "GET", session })
  }

  create(
    session: string,
    body: {
      readonly company_id: string
      readonly title: string
      readonly description?: string
    },
  ): Promise<JobsTransportResponse> {
    return this.#request("/jobs", { method: "POST", session, json: body })
  }

  update(
    session: string,
    jobId: string,
    body: { readonly title?: string; readonly description?: string },
  ): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}`, { method: "PATCH", session, json: body })
  }

  activate(session: string, jobId: string): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}/activate`, { method: "POST", session })
  }

  close(session: string, jobId: string): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}/close`, { method: "POST", session })
  }

  archive(session: string, jobId: string): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}/archive`, { method: "POST", session })
  }

  listMaterials(session: string, jobId: string): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}/materials`, { method: "GET", session })
  }

  async uploadMaterial(
    session: string,
    jobId: string,
    file: Blob,
    filename: string,
  ): Promise<JobsTransportResponse> {
    const form = new FormData()
    form.append("file", file, filename)
    try {
      const response = await ky(new URL(`/jobs/${jobId}/materials`, this.#baseUrl).toString(), {
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
        throw new JobsTransportError("jobs endpoint unavailable")
      }
      throw error
    }
  }

  listEvents(session: string, jobId: string): Promise<JobsTransportResponse> {
    return this.#request(`/jobs/${jobId}/events`, { method: "GET", session })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST" | "PATCH"
      readonly session: string
      readonly json?: unknown
    },
  ): Promise<JobsTransportResponse> {
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
        throw new JobsTransportError("jobs endpoint unavailable")
      }
      throw error
    }
  }
}

export function createJobsTransport(): JobsTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyJobsTransport(baseUrl)
}

export type AccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }
  | { readonly kind: "readOnly" }

export function readJobsErrorDetail(body: unknown): JobsErrorDetail | null {
  const parsed = jobsErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: JobsTransportResponse): AccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    const detail = readJobsErrorDetail(response.body)
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
  return error instanceof JobsTransportError || error instanceof ZodError
}

export type JobsListResult =
  | { readonly kind: "ok"; readonly jobs: readonly JobView[] }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadJobs(
  transport: JobsTransport,
  session: string,
  filters: { readonly status?: JobStatus; readonly companyId?: string },
): Promise<JobsListResult> {
  try {
    const response = await transport.list(session, filters)
    if (response.status === 200) {
      return { kind: "ok", jobs: jobListSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type JobDetailResult =
  | {
      readonly kind: "ok"
      readonly job: JobView
      readonly materials: readonly JobMaterialView[]
      readonly events: readonly JobEventView[]
    }
  | { readonly kind: "notFound" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadJobDetail(
  transport: JobsTransport,
  session: string,
  jobId: string,
): Promise<JobDetailResult> {
  try {
    const [jobResponse, materialsResponse, eventsResponse] = await Promise.all([
      transport.get(session, jobId),
      transport.listMaterials(session, jobId),
      transport.listEvents(session, jobId),
    ])
    if (jobResponse.status === 404) {
      return { kind: "notFound" }
    }
    const denied = accessFailure(jobResponse)
    if (denied) {
      return denied
    }
    if (jobResponse.status !== 200) {
      return { kind: "unreachable" }
    }
    const materials =
      materialsResponse.status === 200 ? jobMaterialListSchema.parse(materialsResponse.body) : []
    const events =
      eventsResponse.status === 200 ? jobEventListSchema.parse(eventsResponse.body) : []
    return {
      kind: "ok",
      job: jobViewSchema.parse(jobResponse.body),
      materials,
      events,
    }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type JobMutationResult =
  | { readonly kind: "ok"; readonly job: JobView }
  | { readonly kind: "notFound" }
  | { readonly kind: "notDraft" }
  | { readonly kind: "statusConflict" }
  | { readonly kind: "quotaExceeded" }
  | { readonly kind: "companyArchived" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function createJob(
  transport: JobsTransport,
  session: string,
  body: {
    readonly company_id: string
    readonly title: string
    readonly description?: string
  },
): Promise<JobMutationResult> {
  try {
    const response = await transport.create(session, body)
    if (response.status === 201) {
      return { kind: "ok", job: jobViewSchema.parse(response.body) }
    }
    if (response.status === 409 && readJobsErrorDetail(response.body) === "company_archived") {
      return { kind: "companyArchived" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function updateJob(
  transport: JobsTransport,
  session: string,
  jobId: string,
  body: { readonly title?: string; readonly description?: string },
): Promise<JobMutationResult> {
  try {
    const response = await transport.update(session, jobId, body)
    if (response.status === 200) {
      return { kind: "ok", job: jobViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409 && readJobsErrorDetail(response.body) === "job_not_draft") {
      return { kind: "notDraft" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function activateJob(
  transport: JobsTransport,
  session: string,
  jobId: string,
): Promise<JobMutationResult> {
  try {
    const response = await transport.activate(session, jobId)
    if (response.status === 200) {
      return { kind: "ok", job: jobViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409) {
      const detail = readJobsErrorDetail(response.body)
      if (detail === "job_quota_exceeded") {
        return { kind: "quotaExceeded" }
      }
      if (detail === "company_archived") {
        return { kind: "companyArchived" }
      }
      return { kind: "statusConflict" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function closeJob(
  transport: JobsTransport,
  session: string,
  jobId: string,
): Promise<JobMutationResult> {
  try {
    const response = await transport.close(session, jobId)
    if (response.status === 200) {
      return { kind: "ok", job: jobViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409) {
      return { kind: "statusConflict" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function archiveJob(
  transport: JobsTransport,
  session: string,
  jobId: string,
): Promise<JobMutationResult> {
  try {
    const response = await transport.archive(session, jobId)
    if (response.status === 200) {
      return { kind: "ok", job: jobViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409) {
      return { kind: "statusConflict" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type MaterialUploadResult =
  | { readonly kind: "ok"; readonly material: JobMaterialView }
  | { readonly kind: "notFound" }
  | { readonly kind: "notDraft" }
  | { readonly kind: "companyArchived" }
  | { readonly kind: "invalidDocument" }
  | { readonly kind: "tooLarge" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function uploadJobMaterial(
  transport: JobsTransport,
  session: string,
  jobId: string,
  file: Blob,
  filename: string,
): Promise<MaterialUploadResult> {
  try {
    const response = await transport.uploadMaterial(session, jobId, file, filename)
    if (response.status === 201) {
      return { kind: "ok", material: jobMaterialSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409) {
      const detail = readJobsErrorDetail(response.body)
      if (detail === "company_archived") {
        return { kind: "companyArchived" }
      }
      return { kind: "notDraft" }
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
