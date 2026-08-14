import { StatusBadge, type StatusMeta } from "@/components/status-badge"
import type { JobStatus } from "@/lib/jobs-contract"

/** jobs 域表格列头统一样式（列表页与详情页共用，ADR 0012/0016）。 */
const jobsTableHeadClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

/** 职位状态 → 展示元信息（列表页与详情页共用，ADR 0012/0024）。 */
const jobStatusMeta: Record<JobStatus, StatusMeta> = {
  draft: { label: "草稿", tone: "outline" },
  active: { label: "活跃", tone: "success" },
  closed: { label: "已关闭", tone: "secondary" },
  archived: { label: "已归档", tone: "secondary" },
}

function JobStatusBadge({ status }: { readonly status: JobStatus }) {
  const meta = jobStatusMeta[status]
  return <StatusBadge label={meta.label} tone={meta.tone} />
}

export { JobStatusBadge, jobStatusMeta, jobsTableHeadClassName }
