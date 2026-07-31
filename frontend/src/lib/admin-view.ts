import type { TenantStatus } from "./admin-contract"

export const tenantStatusLabels: Record<TenantStatus, string> = {
  active: "正常",
  suspended: "已暂停",
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}
