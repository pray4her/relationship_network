import type { StatusMeta } from "@/components/status-badge"
import type { BillingStatus } from "@/lib/billing-contract"
import type { OrderStatus } from "@/lib/orders-contract"
import { orderStatusLabels } from "@/lib/orders-view"

/** 订单状态徽章：待确认→warning，已确认→success，已拒绝→destructive。 */
export const orderStatusMeta: Record<OrderStatus, StatusMeta> = {
  confirmed: { label: orderStatusLabels.confirmed, tone: "success" },
  pending: { label: orderStatusLabels.pending, tone: "warning" },
  rejected: { label: orderStatusLabels.rejected, tone: "destructive" },
}

/** 订阅状态徽章：已订阅→success，试用中→default，已取消/已过期→secondary。 */
export const billingStatusMeta: Record<BillingStatus, StatusMeta> = {
  active: { label: "已订阅", tone: "success" },
  cancelled: { label: "已取消", tone: "secondary" },
  expired: { label: "已过期", tone: "secondary" },
  trialing: { label: "试用中", tone: "default" },
}
