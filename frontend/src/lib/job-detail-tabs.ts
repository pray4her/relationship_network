export const JOB_DETAIL_TABS = [
  "overview",
  "requirement",
  "versions",
  "history",
  "materials",
  "events",
] as const

export type JobDetailTab = (typeof JOB_DETAIL_TABS)[number]

export const JOB_DETAIL_TAB_LABELS: Readonly<Record<JobDetailTab, string>> = {
  overview: "概览",
  requirement: "需求草稿",
  versions: "需求版本",
  history: "需求历史",
  materials: "材料",
  events: "操作记录",
}

export const JOB_DETAIL_EVENTS_PREVIEW_LIMIT = 20

export function isJobDetailTab(value: string | null | undefined): value is JobDetailTab {
  return typeof value === "string" && (JOB_DETAIL_TABS as readonly string[]).includes(value)
}

export function resolveJobDetailTab(
  raw: string | string[] | undefined,
  options: {
    readonly hasEditableDraft: boolean
    readonly matchingBlocked: boolean
  },
): JobDetailTab {
  const candidate = Array.isArray(raw) ? raw[0] : raw
  if (isJobDetailTab(candidate)) {
    return candidate
  }
  if (options.matchingBlocked || options.hasEditableDraft) {
    return "requirement"
  }
  return "overview"
}

export function truncateLabel(value: string, maxLength = 24): string {
  const trimmed = value.trim().replace(/\s+/g, " ")
  if (trimmed.length <= maxLength) {
    return trimmed
  }
  return `${trimmed.slice(0, Math.max(1, maxLength - 1))}…`
}
