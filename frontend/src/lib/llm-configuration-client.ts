import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type LlmAttempt,
  type LlmCandidate,
  type LlmWorkspace,
  llmAttemptSchema,
  llmErrorSchema,
  llmWorkspaceSchema,
} from "./llm-configuration-contract"

const apiUrlSchema = z.url()

export type LlmTransportResponse = { readonly body: unknown; readonly status: number }

export interface LlmConfigurationTransport {
  cancel(session: string, attemptId: string): Promise<LlmTransportResponse>
  copy(
    session: string,
    versionId: string,
    expectedCurrentVersionId: string,
  ): Promise<LlmTransportResponse>
  create(
    session: string,
    candidate: LlmCandidate,
    expectedCurrentVersionId: string,
  ): Promise<LlmTransportResponse>
  read(session: string): Promise<LlmTransportResponse>
}

export class LlmConfigurationTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "LlmConfigurationTransportError"
  }
}

class KyLlmConfigurationTransport implements LlmConfigurationTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  read(session: string): Promise<LlmTransportResponse> {
    return this.#request("/admin/llm-configuration", { method: "GET", session })
  }

  create(
    session: string,
    candidate: LlmCandidate,
    expectedCurrentVersionId: string,
  ): Promise<LlmTransportResponse> {
    return this.#request("/admin/llm-configuration-attempts", {
      json: { ...candidate, expected_current_version_id: expectedCurrentVersionId },
      method: "POST",
      session,
    })
  }

  copy(
    session: string,
    versionId: string,
    expectedCurrentVersionId: string,
  ): Promise<LlmTransportResponse> {
    return this.#request(`/admin/llm-configurations/${versionId}/copy-attempts`, {
      json: { expected_current_version_id: expectedCurrentVersionId },
      method: "POST",
      session,
    })
  }

  cancel(session: string, attemptId: string): Promise<LlmTransportResponse> {
    return this.#request(`/admin/llm-configuration-attempts/${attemptId}/cancel`, {
      method: "POST",
      session,
    })
  }

  async #request(
    path: string,
    options: { readonly json?: unknown; readonly method: "GET" | "POST"; readonly session: string },
  ): Promise<LlmTransportResponse> {
    try {
      const response = await ky(new URL(path, this.#baseUrl), {
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
        throw new LlmConfigurationTransportError("LLM configuration endpoint unavailable")
      }
      throw error
    }
  }
}

export function createLlmConfigurationTransport(): LlmConfigurationTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyLlmConfigurationTransport(baseUrl)
}

export type LlmAccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export type LlmWorkspaceResult =
  | { readonly kind: "ok"; readonly workspace: LlmWorkspace }
  | LlmAccessFailure
  | { readonly kind: "unreachable" }

export type LlmMutationResult =
  | { readonly attempt: LlmAttempt; readonly kind: "ok" }
  | LlmAccessFailure
  | { readonly attemptId: string | null; readonly detail: string; readonly kind: "conflict" }
  | { readonly kind: "notFound" }
  | { readonly kind: "invalid" }
  | { readonly kind: "unreachable" }

function accessFailure(response: LlmTransportResponse): LlmAccessFailure | null {
  if (response.status === 401) return { kind: "anonymous" }
  if (response.status !== 403) return null
  const parsed = llmErrorSchema.safeParse(response.body)
  return parsed.success && parsed.data.detail === "mfa_required"
    ? { kind: "mfaRequired" }
    : { kind: "forbidden" }
}

function expectedFailure(error: unknown): boolean {
  return error instanceof LlmConfigurationTransportError || error instanceof ZodError
}

export async function loadLlmWorkspace(
  transport: LlmConfigurationTransport,
  session: string,
): Promise<LlmWorkspaceResult> {
  try {
    const response = await transport.read(session)
    if (response.status === 200) {
      return { kind: "ok", workspace: llmWorkspaceSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}

async function parseMutation(response: LlmTransportResponse): Promise<LlmMutationResult> {
  const access = accessFailure(response)
  if (access !== null) return access
  if (response.status === 200 || response.status === 202) {
    return { attempt: llmAttemptSchema.parse(response.body), kind: "ok" }
  }
  if (response.status === 409) {
    const parsed = llmErrorSchema.safeParse(response.body)
    return parsed.success
      ? { attemptId: parsed.data.attempt_id ?? null, detail: parsed.data.detail, kind: "conflict" }
      : { kind: "unreachable" }
  }
  if (response.status === 404) return { kind: "notFound" }
  if (response.status === 422) return { kind: "invalid" }
  return { kind: "unreachable" }
}

export async function createLlmAttempt(
  transport: LlmConfigurationTransport,
  session: string,
  candidate: LlmCandidate,
  expectedCurrentVersionId: string,
): Promise<LlmMutationResult> {
  try {
    return await parseMutation(await transport.create(session, candidate, expectedCurrentVersionId))
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}

export async function copyLlmAttempt(
  transport: LlmConfigurationTransport,
  session: string,
  versionId: string,
  expectedCurrentVersionId: string,
): Promise<LlmMutationResult> {
  try {
    return await parseMutation(await transport.copy(session, versionId, expectedCurrentVersionId))
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}

export async function cancelLlmAttempt(
  transport: LlmConfigurationTransport,
  session: string,
  attemptId: string,
): Promise<LlmMutationResult> {
  try {
    return await parseMutation(await transport.cancel(session, attemptId))
  } catch (error) {
    if (expectedFailure(error)) return { kind: "unreachable" }
    throw error
  }
}
