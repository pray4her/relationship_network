import type { OrderStatus } from "./orders-contract"

export const orderStatusLabels: Record<OrderStatus, string> = {
  confirmed: "已确认",
  pending: "待确认",
  rejected: "已拒绝",
}

export function formatAmountCents(amountCents: number): string {
  return `${(amountCents / 100).toFixed(2)} 元`
}
