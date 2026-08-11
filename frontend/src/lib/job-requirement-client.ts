import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import {
  type RequirementErrorDetail,
  type RequirementTask,
  type RequirementWorkspace,
  requirementErrorSchema,
  requirementTaskSchema,
  requirementWorkspaceSchema,
} from "@/lib/job-requirement-contract"

const apiUrlSchema = z.url()

export type RequirementTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface RequirementTransport {
  load(session: string, jobId: string): Promise<RequirementTransportResponse>
  createTask(
    session: string,
    jobId: string,
    idempotencyKey: string,
    sources: readonly { readonly source_id: string; readonly corrected_text: string }[],
  ): Promise<RequirementTransportResponse>
  cancelTask(session: string, jobId: string, taskId: string): Promise<RequirementTransportResponse>
}

export class RequirementTransportError extends Error {}

class KyRequirementTransport implements RequirementTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  load(session: string, jobId: string): Promise<RequirementTransportResponse> {
    return this.#request(`/jobs/${jobId}/requirement-generation`, {
      method: "GET",
      session,
    })
  }

  createTask(
    session: string,
    jobId: string,
    idempotencyKey: string,
    sources: readonly { readonly source_id: string; readonly corrected_text: string }[],
  ): Promise<RequirementTransportResponse> {
    return this.#request(`/jobs/${jobId}/requirement-parsing-tasks`, {
      method: "POST",
      session,
      json: { idempotency_key: idempotencyKey, sources },
    })
  }

  cancelTask(
    session: string,
    jobId: string,
    taskId: string,
  ): Promise<RequirementTransportResponse> {
    return this.#request(`/jobs/${jobId}/requirement-parsing-tasks/${taskId}/cancel`, {
      method: "POST",
      session,
    })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST"
      readonly session: string
      readonly json?: unknown
    },
  ): Promise<RequirementTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl).toString(), {
        cache: "no-store",
        headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` },
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 30_000,
        ...(options.json === undefined ? {} : { json: options.json }),
      })
      const body = await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new RequirementTransportError("requirement generation endpoint unavailable")
      }
      throw error
    }
  }
}

export function createRequirementTransport(): RequirementTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyRequirementTransport(baseUrl)
}

type AccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }
  | { readonly kind: "readOnly" }

function errorDetail(body: unknown): RequirementErrorDetail | null {
  const parsed = requirementErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: RequirementTransportResponse): AccessFailure | null {
  if (response.status === 401) return { kind: "anonymous" }
  if (response.status !== 403) return null
  const detail = errorDetail(response.body)
  if (detail === "mfa_required") return { kind: "mfaRequired" }
  if (detail === "subscription_read_only") return { kind: "readOnly" }
  return { kind: "forbidden" }
}

function expectedError(error: unknown): boolean {
  return error instanceof RequirementTransportError || error instanceof ZodError
}

export type RequirementWorkspaceResult =
  | { readonly kind: "ok"; readonly workspace: RequirementWorkspace }
  | { readonly kind: "notFound" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadRequirementWorkspace(
  transport: RequirementTransport,
  session: string,
  jobId: string,
): Promise<RequirementWorkspaceResult> {
  try {
    const response = await transport.load(session, jobId)
    if (response.status === 200) {
      return { kind: "ok", workspace: requirementWorkspaceSchema.parse(response.body) }
    }
    if (response.status === 404) return { kind: "notFound" }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (expectedError(error)) return { kind: "unreachable" }
    throw error
  }
}

export type CreateRequirementTaskResult =
  | { readonly kind: "ok"; readonly task: RequirementTask }
  | { readonly kind: "businessError"; readonly detail: RequirementErrorDetail }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function createRequirementTask(
  transport: RequirementTransport,
  session: string,
  jobId: string,
  idempotencyKey: string,
  sources: readonly { readonly source_id: string; readonly corrected_text: string }[],
): Promise<CreateRequirementTaskResult> {
  try {
    const response = await transport.createTask(session, jobId, idempotencyKey, sources)
    if (response.status === 202) {
      return { kind: "ok", task: requirementTaskSchema.parse(response.body) }
    }
    const access = accessFailure(response)
    if (access) return access
    const detail = errorDetail(response.body)
    return detail === null ? { kind: "unreachable" } : { kind: "businessError", detail }
  } catch (error) {
    if (expectedError(error)) return { kind: "unreachable" }
    throw error
  }
}

export type CancelRequirementTaskResult =
  | { readonly kind: "ok"; readonly task: RequirementTask }
  | { readonly kind: "businessError"; readonly detail: RequirementErrorDetail }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function cancelRequirementTask(
  transport: RequirementTransport,
  session: string,
  jobId: string,
  taskId: string,
): Promise<CancelRequirementTaskResult> {
  try {
    const response = await transport.cancelTask(session, jobId, taskId)
    if (response.status === 200) {
      return { kind: "ok", task: requirementTaskSchema.parse(response.body) }
    }
    const access = accessFailure(response)
    if (access) return access
    const detail = errorDetail(response.body)
    return detail === null ? { kind: "unreachable" } : { kind: "businessError", detail }
  } catch (error) {
    if (expectedError(error)) return { kind: "unreachable" }
    throw error
  }
}
