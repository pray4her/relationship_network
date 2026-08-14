import type {
  LlmCallMetadataStatus,
  LlmCallOutcome,
  LlmCallScope,
  LlmCallType,
} from "./llm-call-contract"

export const llmCallScopeLabels: Record<LlmCallScope, string> = {
  platform: "平台",
  tenant: "租户",
}

export const llmCallTypeLabels: Record<LlmCallType, string> = {
  config_probe: "配置探测",
  job_requirement_parsing: "职位需求解析",
}

export const llmCallOutcomeLabels: Record<LlmCallOutcome, string> = {
  failed: "失败",
  late_response: "迟到响应",
  outcome_unknown: "结果未知",
  succeeded: "成功",
}

export const llmCallMetadataStatusLabels: Record<LlmCallMetadataStatus, string> = {
  available: "已补齐",
  retry_scheduled: "等待补齐",
  unavailable: "不可用",
}

export function formatDiagnosticCost(value: number | null): string {
  if (value === null) return "—"
  return new Intl.NumberFormat("zh-CN", {
    currency: "USD",
    maximumFractionDigits: 8,
    minimumFractionDigits: 2,
    style: "currency",
  }).format(value)
}

export function displayValue(value: string | number | null): string {
  return value === null || value === "" ? "—" : String(value)
}
