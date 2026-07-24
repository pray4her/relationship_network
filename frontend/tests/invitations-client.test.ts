import { expect, test } from "vitest"

import {
  acceptInvitation,
  createInvitation,
  createInvitationsTransport,
  type InvitationsTransport,
  InvitationsTransportError,
  type InvitationsTransportResponse,
  loadInvitations,
  previewInvitation,
  revokeInvitation,
} from "../src/lib/invitations-client"

const invitationBody = {
  id: "invitation-1",
  email: "invitee@example.com",
  status: "pending",
  expires_at: "2026-07-31T10:20:00Z",
  accepted_at: null,
  revoked_at: null,
  created_at: "2026-07-24T10:20:00Z",
} as const

class ScriptedInvitationsTransport implements InvitationsTransport {
  readonly #handler: () => Promise<InvitationsTransportResponse>

  constructor(handler: () => Promise<InvitationsTransportResponse>) {
    this.#handler = handler
  }

  create(): Promise<InvitationsTransportResponse> {
    return this.#handler()
  }

  list(): Promise<InvitationsTransportResponse> {
    return this.#handler()
  }

  revoke(): Promise<InvitationsTransportResponse> {
    return this.#handler()
  }

  preview(): Promise<InvitationsTransportResponse> {
    return this.#handler()
  }

  accept(): Promise<InvitationsTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: InvitationsTransportResponse): InvitationsTransport {
  return new ScriptedInvitationsTransport(() => Promise.resolve(response))
}

test("creates an invitation and surfaces the one-time link and token", async () => {
  const transport = fixedTransport({
    body: {
      invitation: invitationBody,
      invite_url: "http://localhost:3000/invite/tok",
      token: "tok",
    },
    status: 201,
  })

  const result = await createInvitation(transport, "s", "invitee@example.com")

  expect(result).toEqual({
    kind: "created",
    invitation: invitationBody,
    inviteUrl: "http://localhost:3000/invite/tok",
    token: "tok",
  })
})

test("maps invitation conflicts to dedicated kinds", async () => {
  await expect(
    createInvitation(
      fixedTransport({ body: { detail: "email_already_member" }, status: 409 }),
      "s",
      "invitee@example.com",
    ),
  ).resolves.toEqual({ kind: "alreadyMember" })
  await expect(
    createInvitation(
      fixedTransport({ body: { detail: "invitation_already_pending" }, status: 409 }),
      "s",
      "invitee@example.com",
    ),
  ).resolves.toEqual({ kind: "alreadyPending" })
})

test("parses the invitation list and distinguishes mfa_required", async () => {
  await expect(
    loadInvitations(fixedTransport({ body: [invitationBody], status: 200 }), "s"),
  ).resolves.toEqual({ kind: "ok", invitations: [invitationBody] })
  await expect(
    loadInvitations(fixedTransport({ body: { detail: "mfa_required" }, status: 403 }), "s"),
  ).resolves.toEqual({ kind: "mfaRequired" })
})

test("maps revoke outcomes", async () => {
  await expect(
    revokeInvitation(fixedTransport({ body: invitationBody, status: 200 }), "s", "invitation-1"),
  ).resolves.toEqual({ kind: "revoked", invitation: invitationBody })
  await expect(
    revokeInvitation(
      fixedTransport({ body: { detail: "invitation_not_found" }, status: 404 }),
      "s",
      "invitation-1",
    ),
  ).resolves.toEqual({ kind: "notFound" })
  await expect(
    revokeInvitation(
      fixedTransport({ body: { detail: "invitation_already_accepted" }, status: 409 }),
      "s",
      "invitation-1",
    ),
  ).resolves.toEqual({ kind: "alreadyAccepted" })
})

test("previews an invitation without a session and maps 404 to invalid", async () => {
  const preview = {
    email: "invitee@example.com",
    expires_at: "2026-07-31T10:20:00Z",
    tenant_name: "示例租户",
  }

  await expect(
    previewInvitation(fixedTransport({ body: preview, status: 200 }), "tok"),
  ).resolves.toEqual({ kind: "ok", preview })
  await expect(
    previewInvitation(
      fixedTransport({ body: { detail: "invitation_invalid" }, status: 404 }),
      "bogus",
    ),
  ).resolves.toEqual({ kind: "invalid" })
})

test("maps accept outcomes to dedicated kinds", async () => {
  const acceptance = {
    role: "member",
    tenant_id: "tenant-1",
    tenant_name: "示例租户",
    tenant_slug: "demo",
  }

  await expect(
    acceptInvitation(fixedTransport({ body: acceptance, status: 200 }), "s", "tok"),
  ).resolves.toEqual({ kind: "accepted", acceptance })
  await expect(
    acceptInvitation(
      fixedTransport({ body: { detail: "invitation_email_mismatch" }, status: 403 }),
      "s",
      "tok",
    ),
  ).resolves.toEqual({ kind: "emailMismatch" })
  await expect(
    acceptInvitation(
      fixedTransport({ body: { detail: "already_in_tenant" }, status: 409 }),
      "s",
      "tok",
    ),
  ).resolves.toEqual({ kind: "alreadyInTenant" })
  await expect(
    acceptInvitation(
      fixedTransport({ body: { detail: "not_authenticated" }, status: 401 }),
      "s",
      "tok",
    ),
  ).resolves.toEqual({ kind: "anonymous" })
})

test("reports unreachable when the transport fails", async () => {
  const transport = new ScriptedInvitationsTransport(() =>
    Promise.reject(new InvitationsTransportError("connection failed")),
  )

  await expect(loadInvitations(transport, "s")).resolves.toEqual({ kind: "unreachable" })
})

test("builds a ky transport against the configured base url", () => {
  expect(createInvitationsTransport()).toBeDefined()
})
