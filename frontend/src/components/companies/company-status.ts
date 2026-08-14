import type { StatusMeta } from "@/components/status-badge"
import type { CompanyStatus } from "@/lib/companies-contract"

/** 企业状态徽章：活跃→success，已归档→secondary。 */
export const companyStatusMeta: Record<CompanyStatus, StatusMeta> = {
  active: { label: "活跃", tone: "success" },
  archived: { label: "已归档", tone: "secondary" },
}
