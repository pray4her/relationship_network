import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import {
  assignRolesAction,
  inviteAction,
  memberStatusAction,
  revokeInvitationAction,
} from "@/app/actions/members"
import { AccountPanel } from "@/components/account-panel"
import { InviteForm } from "@/components/members/invite-form"
import { MemberStatusActions } from "@/components/members/member-status-actions"
import { RevokeInvitationButton } from "@/components/members/revoke-invitation-button"
import { RoleAssignment } from "@/components/members/role-assignment"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createInvitationsTransport, loadInvitations } from "@/lib/invitations-client"
import type { InvitationStatus } from "@/lib/invitations-contract"
import { createMembersTransport, loadMembers, loadRoles } from "@/lib/members-client"

export const metadata: Metadata = {
  title: "成员管理 · Relationship Network",
}

const invitationStatusLabels: Record<InvitationStatus, string> = {
  accepted: "已接受",
  expired: "已过期",
  pending: "待接受",
  revoked: "已撤销",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

export default async function MembersPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">成员管理</h1>
          <p className="notice">
            请先<Link href="/login">登录</Link>后查看租户成员。
          </p>
        </section>
      </main>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">成员管理</h1>
          <p className="notice">
            {auth.kind === "anonymous" ? (
              <>
                登录已过期，请<Link href="/login">重新登录</Link>。
              </>
            ) : (
              "服务暂时不可用，请稍后再试。"
            )}
          </p>
        </section>
      </main>
    )
  }

  const permissions = auth.view.permissions
  const canRead = permissions.includes("members:read")
  const canManage = permissions.includes("members:manage")
  const canInvite = permissions.includes("members:invite")

  if (!canRead) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">成员管理</h1>
          <p className="notice">你没有查看租户成员的权限。</p>
        </section>
      </main>
    )
  }

  const membersTransport = createMembersTransport()
  const [membersResult, invitationsResult, rolesResult] = await Promise.all([
    loadMembers(membersTransport, session),
    loadInvitations(createInvitationsTransport(), session),
    canManage
      ? loadRoles(membersTransport, session)
      : Promise.resolve({ kind: "ok", roles: [] } as const),
  ])

  if (membersResult.kind === "mfaRequired" || invitationsResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  if (membersResult.kind !== "ok" || invitationsResult.kind !== "ok") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">成员管理</h1>
          <p className="notice">成员数据暂时不可用，请稍后再试。</p>
        </section>
      </main>
    )
  }

  const roles = rolesResult.kind === "ok" ? rolesResult.roles : []

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="members-heading">
        <h1 className="panel-title" id="members-heading">
          成员列表
        </h1>
        <table className="data-table">
          <thead>
            <tr>
              <th>姓名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>状态</th>
              {canManage ? <th>操作</th> : null}
            </tr>
          </thead>
          <tbody>
            {membersResult.members.map((member) => {
              const isOwner = member.membership_role === "owner"
              return (
                <tr key={member.membership_id}>
                  <td>{member.display_name}</td>
                  <td>{member.email}</td>
                  <td>
                    <span className="tag">{isOwner ? "所有者" : "成员"}</span>
                  </td>
                  <td>
                    <span className={member.is_active ? "tag" : "tag tag-muted"}>
                      {member.is_active ? "正常" : "已停用"}
                    </span>
                  </td>
                  {canManage ? (
                    <td>
                      {isOwner ? null : (
                        <>
                          <MemberStatusActions
                            action={memberStatusAction}
                            isActive={member.is_active}
                            membershipId={member.membership_id}
                          />
                          <RoleAssignment
                            action={assignRolesAction}
                            assignedRoleIds={member.role_ids}
                            membershipId={member.membership_id}
                            roles={roles}
                          />
                        </>
                      )}
                    </td>
                  ) : null}
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      {canInvite ? (
        <section className="panel" aria-labelledby="invite-heading">
          <h2 className="panel-title" id="invite-heading">
            邀请成员
          </h2>
          <InviteForm action={inviteAction} />
        </section>
      ) : null}

      <section className="panel" aria-labelledby="invitations-heading">
        <h2 className="panel-title" id="invitations-heading">
          邀请记录
        </h2>
        {invitationsResult.invitations.length === 0 ? (
          <p className="field-hint">暂无邀请记录。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>邮箱</th>
                <th>状态</th>
                <th>过期时间</th>
                {canInvite ? <th>操作</th> : null}
              </tr>
            </thead>
            <tbody>
              {invitationsResult.invitations.map((invitation) => (
                <tr key={invitation.id}>
                  <td>{invitation.email}</td>
                  <td>
                    <span className="tag">{invitationStatusLabels[invitation.status]}</span>
                  </td>
                  <td>{formatDateTime(invitation.expires_at)}</td>
                  {canInvite ? (
                    <td>
                      {invitation.status === "pending" ? (
                        <RevokeInvitationButton
                          action={revokeInvitationAction}
                          invitationId={invitation.id}
                        />
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  )
}
