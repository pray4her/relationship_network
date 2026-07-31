import { render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { loadAuthSession } from "@/lib/auth-client"
import { loadInvitations } from "@/lib/invitations-client"
import { loadMembers, loadRoles } from "@/lib/members-client"
import MembersPage from "../src/app/members/page"

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: () => ({ value: "session-token" }),
  }),
}))

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}))

vi.mock("@/components/account-panel", () => ({
  AccountPanel: () => null,
}))

vi.mock("@/lib/auth-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-client")>()
  return {
    ...actual,
    createAuthTransport: vi.fn(() => ({})),
    loadAuthSession: vi.fn(),
  }
})

vi.mock("@/lib/members-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/members-client")>()
  return {
    ...actual,
    createMembersTransport: vi.fn(() => ({})),
    loadMembers: vi.fn(),
    loadRoles: vi.fn(),
  }
})

vi.mock("@/lib/invitations-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/invitations-client")>()
  return {
    ...actual,
    createInvitationsTransport: vi.fn(() => ({})),
    loadInvitations: vi.fn(),
  }
})

const mockedLoadAuthSession = vi.mocked(loadAuthSession)
const mockedLoadMembers = vi.mocked(loadMembers)
const mockedLoadRoles = vi.mocked(loadRoles)
const mockedLoadInvitations = vi.mocked(loadInvitations)

beforeEach(() => {
  vi.clearAllMocks()
})

const ownerMember = {
  membership_id: "membership-owner",
  user_id: "user-owner",
  email: "owner@example.com",
  display_name: "张三",
  membership_role: "owner",
  is_active: true,
  role_ids: [] as string[],
} as const

const plainMember = {
  membership_id: "membership-1",
  user_id: "user-1",
  email: "member@example.com",
  display_name: "李四",
  membership_role: "member",
  is_active: true,
  role_ids: [] as string[],
} as const

function stubSession(permissions: readonly string[]) {
  mockedLoadAuthSession.mockResolvedValue({
    kind: "authenticated",
    renewedSession: null,
    view: {
      permissions: [...permissions],
      role: "owner",
      tenant: { id: "tenant-1", name: "示例租户", slug: "demo" },
      user: {
        display_name: "张三",
        email: "owner@example.com",
        id: "user-owner",
        is_platform_admin: false,
      },
    },
  })
}

test("hides member actions without the members:manage permission", async () => {
  // Given a session that may read but not manage members
  stubSession(["members:read", "members:invite"])
  mockedLoadMembers.mockResolvedValue({ kind: "ok", members: [ownerMember, plainMember] })
  mockedLoadInvitations.mockResolvedValue({ kind: "ok", invitations: [] })

  // When the members page renders
  render(await MembersPage())

  // Then the roster is visible but no management controls are offered
  expect(screen.getByText("李四")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "停用" })).not.toBeInTheDocument()
  expect(screen.queryByText("分配角色")).not.toBeInTheDocument()
})

test("offers no actions for the protected owner row", async () => {
  // Given a fully privileged session
  stubSession(["members:read", "members:manage", "members:invite", "roles:read"])
  mockedLoadMembers.mockResolvedValue({ kind: "ok", members: [ownerMember, plainMember] })
  mockedLoadInvitations.mockResolvedValue({ kind: "ok", invitations: [] })
  mockedLoadRoles.mockResolvedValue({ kind: "ok", roles: [] })

  // When the members page renders
  render(await MembersPage())

  // Then the regular member row has actions while the owner row has none
  expect(screen.getAllByRole("button", { name: "停用" })).toHaveLength(1)
  expect(screen.getAllByRole("button", { name: "移除" })).toHaveLength(1)
  const ownerRow = screen.getByText("张三").closest("tr")
  expect(ownerRow?.textContent).not.toContain("停用")
  expect(ownerRow?.textContent).not.toContain("分配角色")
})

test("denies the page entirely without the members:read permission", async () => {
  stubSession([])
  render(await MembersPage())

  expect(screen.getByText("你没有查看租户成员的权限。")).toBeInTheDocument()
  expect(mockedLoadMembers).not.toHaveBeenCalled()
})
