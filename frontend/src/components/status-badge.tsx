import { Badge } from "@/components/ui/badge"

/** 状态语义色（功能色），不承担品牌表达。 */
type StatusTone = "default" | "secondary" | "destructive" | "outline" | "success" | "warning"

type StatusMeta = { readonly label: string; readonly tone: StatusTone }

/**
 * 状态徽章唯一入口（ADR 0012/0024）。
 * 页面不得再用 `bg-success/10 text-success` 等手写类覆盖 Badge。
 * 各域的 status → StatusMeta 映射定义在该域的共享模块中。
 */
function StatusBadge({ label, tone }: { readonly label: string; readonly tone: StatusTone }) {
  return <Badge variant={tone}>{label}</Badge>
}

export type { StatusMeta, StatusTone }
export { StatusBadge }
