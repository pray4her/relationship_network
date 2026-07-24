import { expect, test } from "vitest"

import {
  assignMemberRoles,
  deactivateMember,
  loadMembers,
  loadRoles,
  type MembersTransport,
  MembersTransportError,
  type MembersTransportResponse,
  removeMember,
} from "../src/lib/members-client"

const memberBody = {
  membership_id: "membership-1",
  user_id: "user-1",
  email: "member@example.com",
  display_name: "李四",
  membership_role: "member",
  is_active: true,
  role_ids: ["role-1"],
} as const

const roleBody = {
  id: "role-1",
  name: "管理员",
  description: "负责日常管理",
  is_active: true,
  permissions: ["members:manage"],
} as const

class ScriptedMembersTransport implements MembersTransport {
  readonly #handler: () => Promise<MembersTransportResponse>

  constructor(handler: () => Promise<MembersTransportResponse>) {
    this.#handler = handler
  }

  listMembers(): Promise<MembersTransportResponse> {
    return this.#handler()
  }

  listRoles(): Promise<MembersTransportResponse> {
    return this.#handler()
  }

  deactivate(): Promise<MembersTransportResponse> {
    return this.#handler()
  }

  activate(): Promise<MembersTransportResponse> {
    return this.#handler()
  }

  remove(): Promise<MembersTransportResponse> {
    return this.#handler()
  }

  assignRoles(): Promise<MembersTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: MembersTransportResponse): MembersTransport {
  return new ScriptedMembersTransport(() => Promise.resolve(response))
}

function failingTransport(): MembersTransport {
  return new ScriptedMembersTransport(() =>
    Promise.reject(new MembersTransportError("connection failed")),
  )
}

test("parses the member list on success", async () => {
  const result = await loadMembers(fixedTransport({ body: [memberBody], status: 200 }), "s")

  expect(result).toEqual({ kind: "ok", members: [memberBody] })
})

test("distinguishes mfa_required from a plain permission failure", async () => {
  await expect(
    loadMembers(fixedTransport({ body: { detail: "mfa_required" }, status: 403 }), "s"),
  ).resolves.toEqual({ kind: "mfaRequired" })
  await expect(
    loadMembers(fixedTransport({ body: { detail: "permission_denied" }, status: 403 }), "s"),
  ).resolves.toEqual({ kind: "forbidden" })
  await expect(
    loadMembers(fixedTransport({ body: { detail: "not_authenticated" }, status: 401 }), "s"),
  ).resolves.toEqual({ kind: "anonymous" })
})

test("parses the role list on success", async () => {
  const result = await loadRoles(fixedTransport({ body: [roleBody], status: 200 }), "s")

  expect(result).toEqual({ kind: "ok", roles: [roleBody] })
})

test("maps deactivate success and protected-owner failure", async () => {
  await expect(
    deactivateMember(fixedTransport({ body: memberBody, status: 200 }), "s", "membership-1"),
  ).resolves.toEqual({ kind: "ok", member: memberBody })
  await expect(
    deactivateMember(
      fixedTransport({ body: { detail: "protected_owner" }, status: 403 }),
      "s",
      "membership-1",
    ),
  ).resolves.toEqual({ kind: "protectedOwner" })
})

test("maps remove success and membership-not-found failure", async () => {
  await expect(
    removeMember(fixedTransport({ body: null, status: 204 }), "s", "membership-1"),
  ).resolves.toEqual({ kind: "removed" })
  await expect(
    removeMember(
      fixedTransport({ body: { detail: "membership_not_found" }, status: 404 }),
      "s",
      "membership-1",
    ),
  ).resolves.toEqual({ kind: "notFound" })
})

test("maps assign-roles success and transport failures", async () => {
  await expect(
    assignMemberRoles(fixedTransport({ body: memberBody, status: 200 }), "s", "membership-1", [
      "role-1",
    ]),
  ).resolves.toEqual({ kind: "ok", member: memberBody })
  await expect(
    assignMemberRoles(failingTransport(), "s", "membership-1", ["role-1"]),
  ).resolves.toEqual({ kind: "unreachable" })
})

test("treats an out-of-contract member list as unreachable", async () => {
  const result = await loadMembers(fixedTransport({ body: [{ nope: true }], status: 200 }), "s")

  expect(result).toEqual({ kind: "unreachable" })
})
