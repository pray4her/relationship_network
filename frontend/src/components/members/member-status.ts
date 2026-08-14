import type { StatusMeta } from "@/components/status-badge"
import type { InvitationStatus } from "@/lib/invitations-contract"
import type { MemberView } from "@/lib/members-contract"

/** 成员角色徽章：所有者→default，成员→secondary。 */
export const memberRoleMeta: Record<MemberView["membership_role"], StatusMeta> = {
  member: { label: "成员", tone: "secondary" },
  owner: { label: "所有者", tone: "default" },
}

/** 成员状态徽章：正常→success，已停用→secondary。 */
export function memberStatusMeta(isActive: boolean): StatusMeta {
  return isActive ? { label: "正常", tone: "success" } : { label: "已停用", tone: "secondary" }
}

/** 邀请状态徽章：已接受→success，待接受→default，已过期/已撤销→secondary。 */
export const invitationStatusMeta: Record<InvitationStatus, StatusMeta> = {
  accepted: { label: "已接受", tone: "success" },
  expired: { label: "已过期", tone: "secondary" },
  pending: { label: "待接受", tone: "default" },
  revoked: { label: "已撤销", tone: "secondary" },
}
