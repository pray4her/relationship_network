import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type InvitationAcceptance,
  type InvitationPreview,
  type InvitationView,
  invitationAcceptanceSchema,
  invitationCreateSchema,
  invitationListSchema,
  invitationPreviewSchema,
  invitationsErrorSchema,
  invitationViewSchema,
} from "./invitations-contract"

const apiUrlSchema = z.url()

export type InvitationsTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface InvitationsTransport {
  create(session: string, email: string): Promise<InvitationsTransportResponse>
  list(session: string): Promise<InvitationsTransportResponse>
  revoke(session: string, invitationId: string): Promise<InvitationsTransportResponse>
  preview(token: string): Promise<InvitationsTransportResponse>
  accept(session: string, token: string): Promise<InvitationsTransportResponse>
}

export class InvitationsTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "InvitationsTransportError"
  }
}

class KyInvitationsTransport implements InvitationsTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  create(session: string, email: string): Promise<InvitationsTransportResponse> {
    return this.#request("/invitations", { json: { email }, method: "POST", session })
  }

  list(session: string): Promise<InvitationsTransportResponse> {
    return this.#request("/invitations", { method: "GET", session })
  }

  revoke(session: string, invitationId: string): Promise<InvitationsTransportResponse> {
    return this.#request(`/invitations/${invitationId}/revoke`, { method: "POST", session })
  }

  preview(token: string): Promise<InvitationsTransportResponse> {
    const url = new URL("/invitations/preview", this.#baseUrl)
    url.searchParams.set("token", token)
    return this.#request(url.toString(), { method: "GET" })
  }

  accept(session: string, token: string): Promise<InvitationsTransportResponse> {
    return this.#request("/invitations/accept", { json: { token }, method: "POST", session })
  }

  async #request(
    pathOrUrl: string,
    options: {
      readonly method: "GET" | "POST"
      readonly session?: string
      readonly json?: unknown
    },
  ): Promise<InvitationsTransportResponse> {
    try {
      const url = pathOrUrl.startsWith("http")
        ? pathOrUrl
        : new URL(pathOrUrl, this.#baseUrl).toString()
      const response = await ky(url, {
        cache: "no-store",
        method: options.method,
        retry: 0,
        throwHttpErrors: false,
        timeout: 10_000,
        ...(options.session === undefined
          ? {}
          : { headers: { cookie: `${SESSION_COOKIE_NAME}=${options.session}` } }),
        ...(options.json === undefined ? {} : { json: options.json }),
      })
      const body = response.status === 204 ? null : await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new InvitationsTransportError("invitations endpoint unavailable")
      }
      throw error
    }
  }
}

export function createInvitationsTransport(): InvitationsTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyInvitationsTransport(baseUrl)
}

function readErrorDetail(body: unknown) {
  const parsed = invitationsErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof InvitationsTransportError || error instanceof ZodError
}

export type InvitationAccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

function accessFailure(response: InvitationsTransportResponse): InvitationAccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    return readErrorDetail(response.body) === "mfa_required"
      ? { kind: "mfaRequired" }
      : { kind: "forbidden" }
  }
  return null
}

export type CreateInvitationResult =
  | {
      readonly kind: "created"
      readonly invitation: InvitationView
      readonly token: string
      readonly inviteUrl: string
    }
  | { readonly kind: "alreadyMember" }
  | { readonly kind: "alreadyPending" }
  | InvitationAccessFailure
  | { readonly kind: "unreachable" }

export async function createInvitation(
  transport: InvitationsTransport,
  session: string,
  email: string,
): Promise<CreateInvitationResult> {
  try {
    const response = await transport.create(session, email)
    if (response.status === 201) {
      const parsed = invitationCreateSchema.parse(response.body)
      return {
        kind: "created",
        invitation: parsed.invitation,
        inviteUrl: parsed.invite_url,
        token: parsed.token,
      }
    }
    if (response.status === 409) {
      const detail = readErrorDetail(response.body)
      if (detail === "email_already_member") {
        return { kind: "alreadyMember" }
      }
      if (detail === "invitation_already_pending") {
        return { kind: "alreadyPending" }
      }
      return { kind: "unreachable" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type InvitationsResult =
  | { readonly kind: "ok"; readonly invitations: readonly InvitationView[] }
  | InvitationAccessFailure
  | { readonly kind: "unreachable" }

export async function loadInvitations(
  transport: InvitationsTransport,
  session: string,
): Promise<InvitationsResult> {
  try {
    const response = await transport.list(session)
    if (response.status === 200) {
      return { kind: "ok", invitations: invitationListSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type RevokeInvitationResult =
  | { readonly kind: "revoked"; readonly invitation: InvitationView }
  | { readonly kind: "notFound" }
  | { readonly kind: "alreadyAccepted" }
  | InvitationAccessFailure
  | { readonly kind: "unreachable" }

export async function revokeInvitation(
  transport: InvitationsTransport,
  session: string,
  invitationId: string,
): Promise<RevokeInvitationResult> {
  try {
    const response = await transport.revoke(session, invitationId)
    if (response.status === 200) {
      return { kind: "revoked", invitation: invitationViewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "notFound" }
    }
    if (response.status === 409) {
      return readErrorDetail(response.body) === "invitation_already_accepted"
        ? { kind: "alreadyAccepted" }
        : { kind: "unreachable" }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type PreviewInvitationResult =
  | { readonly kind: "ok"; readonly preview: InvitationPreview }
  | { readonly kind: "invalid" }
  | { readonly kind: "unreachable" }

export async function previewInvitation(
  transport: InvitationsTransport,
  token: string,
): Promise<PreviewInvitationResult> {
  try {
    const response = await transport.preview(token)
    if (response.status === 200) {
      return { kind: "ok", preview: invitationPreviewSchema.parse(response.body) }
    }
    if (response.status === 404) {
      return { kind: "invalid" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type AcceptInvitationResult =
  | { readonly kind: "accepted"; readonly acceptance: InvitationAcceptance }
  | { readonly kind: "invalid" }
  | { readonly kind: "emailMismatch" }
  | { readonly kind: "alreadyInTenant" }
  | { readonly kind: "anonymous" }
  | { readonly kind: "unreachable" }

export async function acceptInvitation(
  transport: InvitationsTransport,
  session: string,
  token: string,
): Promise<AcceptInvitationResult> {
  try {
    const response = await transport.accept(session, token)
    if (response.status === 200) {
      return { kind: "accepted", acceptance: invitationAcceptanceSchema.parse(response.body) }
    }
    if (response.status === 401) {
      return { kind: "anonymous" }
    }
    if (response.status === 404) {
      return { kind: "invalid" }
    }
    if (response.status === 403) {
      return readErrorDetail(response.body) === "invitation_email_mismatch"
        ? { kind: "emailMismatch" }
        : { kind: "unreachable" }
    }
    if (response.status === 409) {
      return readErrorDetail(response.body) === "already_in_tenant"
        ? { kind: "alreadyInTenant" }
        : { kind: "unreachable" }
    }
    return { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
