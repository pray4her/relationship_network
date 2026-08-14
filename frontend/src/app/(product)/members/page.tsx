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
import {
  DataRegion,
  DataRegionContent,
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { InviteForm } from "@/components/members/invite-form"
import {
  invitationStatusMeta,
  memberRoleMeta,
  memberStatusMeta,
} from "@/components/members/member-status"
import { MemberStatusActions } from "@/components/members/member-status-actions"
import { RevokeInvitationButton } from "@/components/members/revoke-invitation-button"
import { RoleAssignment } from "@/components/members/role-assignment"
import { StatusBadge } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { formatDateTime } from "@/lib/format"
import { createInvitationsTransport, loadInvitations } from "@/lib/invitations-client"
import { createMembersTransport, loadMembers, loadRoles } from "@/lib/members-client"

export const metadata: Metadata = {
  title: "成员管理",
}

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>成员管理</PageTitle>
          <PageDescription>查看成员、分配角色并管理租户邀请。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

export default async function MembersPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
          登录
        </Link>
        后查看租户成员。
      </NoticePage>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <NoticePage>
        {auth.kind === "anonymous" ? (
          <>
            登录已过期，请
            <Link className="font-medium underline underline-offset-4" href="/login">
              重新登录
            </Link>
            。
          </>
        ) : (
          "服务暂时不可用，请稍后再试。"
        )}
      </NoticePage>
    )
  }

  const permissions = auth.view.permissions

  if (auth.view.tenant === null) {
    return <NoticePage>你没有加入任何租户，无法查看租户成员。</NoticePage>
  }

  const canRead = permissions.includes("members:read")
  const canManage = permissions.includes("members:manage")
  const canInvite = permissions.includes("members:invite")

  if (!canRead) {
    return <NoticePage>你没有查看租户成员的权限。</NoticePage>
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
    return <NoticePage>成员数据暂时不可用，请稍后再试。</NoticePage>
  }

  const roles = rolesResult.kind === "ok" ? rolesResult.roles : []

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>成员管理</PageTitle>
          <PageDescription>查看成员、分配角色并管理租户邀请。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <PageSection aria-labelledby="members-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="members-heading">成员列表</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className={headClassName}>姓名</TableHead>
                  <TableHead className={headClassName}>邮箱</TableHead>
                  <TableHead className={headClassName}>角色</TableHead>
                  <TableHead className={headClassName}>状态</TableHead>
                  {canManage ? <TableHead className={headClassName}>操作</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {membersResult.members.map((member) => {
                  const isOwner = member.membership_role === "owner"
                  return (
                    <TableRow key={member.membership_id}>
                      <TableCell>{member.display_name}</TableCell>
                      <TableCell>{member.email}</TableCell>
                      <TableCell>
                        <StatusBadge {...memberRoleMeta[member.membership_role]} />
                      </TableCell>
                      <TableCell>
                        <StatusBadge {...memberStatusMeta(member.is_active)} />
                      </TableCell>
                      {canManage ? (
                        <TableCell>
                          {isOwner ? (
                            <span className="text-sm text-muted-foreground">所有者不可操作</span>
                          ) : (
                            <div className="flex flex-col items-start gap-2">
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
                            </div>
                          )}
                        </TableCell>
                      ) : null}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </DataRegionContent>
        </DataRegion>
      </PageSection>

      {canInvite ? (
        <FormSection aria-labelledby="invite-heading">
          <FormSectionHeader>
            <FormSectionTitle id="invite-heading">邀请成员</FormSectionTitle>
            <FormSectionDescription>向新成员发送限时邀请。</FormSectionDescription>
          </FormSectionHeader>
          <FormSectionContent>
            <InviteForm action={inviteAction} />
          </FormSectionContent>
        </FormSection>
      ) : null}

      <PageSection aria-labelledby="invitations-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="invitations-heading">邀请记录</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {invitationsResult.invitations.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>暂无邀请记录</EmptyTitle>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={headClassName}>邮箱</TableHead>
                    <TableHead className={headClassName}>状态</TableHead>
                    <TableHead className={headClassName}>过期时间</TableHead>
                    {canInvite ? <TableHead className={headClassName}>操作</TableHead> : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invitationsResult.invitations.map((invitation) => (
                    <TableRow key={invitation.id}>
                      <TableCell>{invitation.email}</TableCell>
                      <TableCell>
                        <StatusBadge {...invitationStatusMeta[invitation.status]} />
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatDateTime(invitation.expires_at)}
                      </TableCell>
                      {canInvite ? (
                        <TableCell>
                          {invitation.status === "pending" ? (
                            <RevokeInvitationButton
                              action={revokeInvitationAction}
                              invitationId={invitation.id}
                            />
                          ) : null}
                        </TableCell>
                      ) : null}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
