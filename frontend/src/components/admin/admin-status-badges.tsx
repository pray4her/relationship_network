import { StatusBadge, type StatusMeta } from "@/components/status-badge"
import type { TenantStatus } from "@/lib/admin-contract"
import { tenantStatusLabels } from "@/lib/admin-view"
import type { LlmCallMetadataStatus, LlmCallOutcome } from "@/lib/llm-call-contract"
import { llmCallMetadataStatusLabels, llmCallOutcomeLabels } from "@/lib/llm-call-view"
import type { LlmAttemptStatus } from "@/lib/llm-configuration-contract"
import type { OrderStatus } from "@/lib/orders-contract"
import { orderStatusLabels } from "@/lib/orders-view"

/** admin 域表格表头统一风格（mono/大写）。 */
export const adminTableHeadClassName =
  "font-mono text-xs tracking-wider text-muted-foreground uppercase"

const tenantStatusMeta: Record<TenantStatus, StatusMeta> = {
  active: { label: tenantStatusLabels.active, tone: "success" },
  suspended: { label: tenantStatusLabels.suspended, tone: "warning" },
}

export function TenantStatusBadge({ status }: { readonly status: TenantStatus }) {
  const meta = tenantStatusMeta[status]
  return <StatusBadge label={meta.label} tone={meta.tone} />
}

const orderStatusMeta: Record<OrderStatus, StatusMeta> = {
  confirmed: { label: orderStatusLabels.confirmed, tone: "success" },
  pending: { label: orderStatusLabels.pending, tone: "warning" },
  rejected: { label: orderStatusLabels.rejected, tone: "destructive" },
}

export function OrderStatusBadge({ status }: { readonly status: OrderStatus }) {
  const meta = orderStatusMeta[status]
  return <StatusBadge label={meta.label} tone={meta.tone} />
}

const llmCallOutcomeMeta: Record<LlmCallOutcome, StatusMeta> = {
  failed: { label: llmCallOutcomeLabels.failed, tone: "destructive" },
  late_response: { label: llmCallOutcomeLabels.late_response, tone: "warning" },
  outcome_unknown: { label: llmCallOutcomeLabels.outcome_unknown, tone: "warning" },
  succeeded: { label: llmCallOutcomeLabels.succeeded, tone: "success" },
}

export function LlmCallOutcomeBadge({ outcome }: { readonly outcome: LlmCallOutcome | null }) {
  if (outcome === null) return <StatusBadge label="等待结果" tone="outline" />
  const meta = llmCallOutcomeMeta[outcome]
  return <StatusBadge label={meta.label} tone={meta.tone} />
}

const llmCallMetadataStatusMeta: Record<LlmCallMetadataStatus, StatusMeta> = {
  available: { label: llmCallMetadataStatusLabels.available, tone: "success" },
  retry_scheduled: { label: llmCallMetadataStatusLabels.retry_scheduled, tone: "secondary" },
  unavailable: { label: llmCallMetadataStatusLabels.unavailable, tone: "warning" },
}

export function LlmCallMetadataStatusBadge({
  status,
}: {
  readonly status: LlmCallMetadataStatus | null
}) {
  if (status === null) return <StatusBadge label="等待元数据" tone="outline" />
  const meta = llmCallMetadataStatusMeta[status]
  return <StatusBadge label={meta.label} tone={meta.tone} />
}

const llmAttemptStatusMeta: Record<LlmAttemptStatus, StatusMeta> = {
  cancel_requested: { label: "正在取消", tone: "warning" },
  cancelled: { label: "已取消", tone: "secondary" },
  conflicted: { label: "配置冲突", tone: "secondary" },
  failed: { label: "探测失败", tone: "destructive" },
  queued: { label: "等待执行", tone: "secondary" },
  retry_scheduled: { label: "等待重试", tone: "warning" },
  running: { label: "正在探测", tone: "secondary" },
  succeeded: { label: "已启用", tone: "success" },
}

export function LlmAttemptStatusBadge({ status }: { readonly status: LlmAttemptStatus }) {
  const meta = llmAttemptStatusMeta[status]
  return <StatusBadge label={meta.label} tone={meta.tone} />
}
