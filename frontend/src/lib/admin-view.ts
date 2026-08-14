import type { TenantStatus } from "./admin-contract"

export const tenantStatusLabels: Record<TenantStatus, string> = {
  active: "正常",
  suspended: "已暂停",
}
