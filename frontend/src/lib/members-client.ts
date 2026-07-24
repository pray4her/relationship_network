import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { SESSION_COOKIE_NAME } from "./auth-client"
import {
  type MemberView,
  memberListSchema,
  membersErrorSchema,
  memberViewSchema,
  type RoleView,
  roleListSchema,
} from "./members-contract"

const apiUrlSchema = z.url()

export type MembersTransportResponse = {
  readonly status: number
  readonly body: unknown
}

export interface MembersTransport {
  listMembers(session: string): Promise<MembersTransportResponse>
  listRoles(session: string): Promise<MembersTransportResponse>
  deactivate(session: string, membershipId: string): Promise<MembersTransportResponse>
  activate(session: string, membershipId: string): Promise<MembersTransportResponse>
  remove(session: string, membershipId: string): Promise<MembersTransportResponse>
  assignRoles(
    session: string,
    membershipId: string,
    roleIds: readonly string[],
  ): Promise<MembersTransportResponse>
}

export class MembersTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "MembersTransportError"
  }
}

class KyMembersTransport implements MembersTransport {
  readonly #baseUrl: string

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl
  }

  listMembers(session: string): Promise<MembersTransportResponse> {
    return this.#request("/members", { method: "GET", session })
  }

  listRoles(session: string): Promise<MembersTransportResponse> {
    return this.#request("/roles", { method: "GET", session })
  }

  deactivate(session: string, membershipId: string): Promise<MembersTransportResponse> {
    return this.#request(`/members/${membershipId}/deactivate`, { method: "POST", session })
  }

  activate(session: string, membershipId: string): Promise<MembersTransportResponse> {
    return this.#request(`/members/${membershipId}/activate`, { method: "POST", session })
  }

  remove(session: string, membershipId: string): Promise<MembersTransportResponse> {
    return this.#request(`/members/${membershipId}`, { method: "DELETE", session })
  }

  assignRoles(
    session: string,
    membershipId: string,
    roleIds: readonly string[],
  ): Promise<MembersTransportResponse> {
    return this.#request(`/members/${membershipId}/roles`, {
      json: { role_ids: roleIds },
      method: "PUT",
      session,
    })
  }

  async #request(
    path: string,
    options: {
      readonly method: "GET" | "POST" | "PUT" | "DELETE"
      readonly session: string
      readonly json?: unknown
    },
  ): Promise<MembersTransportResponse> {
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
      const body = response.status === 204 ? null : await response.json<unknown>().catch(() => null)
      return { body, status: response.status }
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new MembersTransportError("members endpoint unavailable")
      }
      throw error
    }
  }
}

export function createMembersTransport(): MembersTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyMembersTransport(baseUrl)
}

export type AccessFailure =
  | { readonly kind: "anonymous" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "mfaRequired" }

export function readMembersErrorDetail(body: unknown) {
  const parsed = membersErrorSchema.safeParse(body)
  return parsed.success ? parsed.data.detail : null
}

function accessFailure(response: MembersTransportResponse): AccessFailure | null {
  if (response.status === 401) {
    return { kind: "anonymous" }
  }
  if (response.status === 403) {
    return readMembersErrorDetail(response.body) === "mfa_required"
      ? { kind: "mfaRequired" }
      : { kind: "forbidden" }
  }
  return null
}

function isExpectedError(error: unknown): boolean {
  return error instanceof MembersTransportError || error instanceof ZodError
}

export type MembersResult =
  | { readonly kind: "ok"; readonly members: readonly MemberView[] }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadMembers(
  transport: MembersTransport,
  session: string,
): Promise<MembersResult> {
  try {
    const response = await transport.listMembers(session)
    if (response.status === 200) {
      return { kind: "ok", members: memberListSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type RolesResult =
  | { readonly kind: "ok"; readonly roles: readonly RoleView[] }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function loadRoles(
  transport: MembersTransport,
  session: string,
): Promise<RolesResult> {
  try {
    const response = await transport.listRoles(session)
    if (response.status === 200) {
      return { kind: "ok", roles: roleListSchema.parse(response.body) }
    }
    return accessFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export type MemberMutationResult =
  | { readonly kind: "ok"; readonly member: MemberView }
  | { readonly kind: "notFound" }
  | { readonly kind: "protectedOwner" }
  | AccessFailure
  | { readonly kind: "unreachable" }

type MemberMutationFailure =
  | { readonly kind: "notFound" }
  | { readonly kind: "protectedOwner" }
  | AccessFailure

function memberMutationFailure(response: MembersTransportResponse): MemberMutationFailure | null {
  if (response.status === 403 && readMembersErrorDetail(response.body) === "protected_owner") {
    return { kind: "protectedOwner" }
  }
  if (response.status === 404) {
    return { kind: "notFound" }
  }
  return accessFailure(response)
}

async function mutateMember(
  request: () => Promise<MembersTransportResponse>,
): Promise<MemberMutationResult> {
  try {
    const response = await request()
    if (response.status === 200) {
      return { kind: "ok", member: memberViewSchema.parse(response.body) }
    }
    return memberMutationFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}

export async function deactivateMember(
  transport: MembersTransport,
  session: string,
  membershipId: string,
): Promise<MemberMutationResult> {
  return mutateMember(() => transport.deactivate(session, membershipId))
}

export async function activateMember(
  transport: MembersTransport,
  session: string,
  membershipId: string,
): Promise<MemberMutationResult> {
  return mutateMember(() => transport.activate(session, membershipId))
}

export async function assignMemberRoles(
  transport: MembersTransport,
  session: string,
  membershipId: string,
  roleIds: readonly string[],
): Promise<MemberMutationResult> {
  return mutateMember(() => transport.assignRoles(session, membershipId, roleIds))
}

export type RemoveMemberResult =
  | { readonly kind: "removed" }
  | { readonly kind: "notFound" }
  | { readonly kind: "protectedOwner" }
  | AccessFailure
  | { readonly kind: "unreachable" }

export async function removeMember(
  transport: MembersTransport,
  session: string,
  membershipId: string,
): Promise<RemoveMemberResult> {
  try {
    const response = await transport.remove(session, membershipId)
    if (response.status === 204) {
      return { kind: "removed" }
    }
    return memberMutationFailure(response) ?? { kind: "unreachable" }
  } catch (error) {
    if (isExpectedError(error)) {
      return { kind: "unreachable" }
    }
    throw error
  }
}
