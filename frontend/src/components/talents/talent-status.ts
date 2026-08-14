import type { StatusMeta } from "@/components/status-badge"
import type { TalentAvailability } from "@/lib/talents-contract"

/** 人才可用性徽章：可用→success，暂时不可用→warning。 */
export const talentStatusMeta: Record<TalentAvailability, StatusMeta> = {
  available: { label: "可用", tone: "success" },
  temporarily_unavailable: { label: "暂时不可用", tone: "warning" },
}
