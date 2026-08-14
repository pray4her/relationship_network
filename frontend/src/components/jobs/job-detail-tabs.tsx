"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { type ReactNode, useTransition } from "react"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { isJobDetailTab, JOB_DETAIL_TAB_LABELS, type JobDetailTab } from "@/lib/job-detail-tabs"

type JobDetailTabCounts = {
  readonly materials?: number
  readonly unsupported?: number
  readonly versions?: number
  readonly events?: number
}

type JobDetailTabsProps = {
  readonly activeTab: JobDetailTab
  readonly counts?: JobDetailTabCounts
  readonly overview: ReactNode
  readonly requirement: ReactNode
  readonly versions: ReactNode
  readonly history: ReactNode
  readonly materials: ReactNode
  readonly events: ReactNode
}

function TabCount({ value }: { readonly value: number | undefined }) {
  if (value === undefined || value <= 0) {
    return null
  }
  return (
    <Badge className="tabular-nums" variant="secondary">
      {value.toLocaleString("zh-CN")}
    </Badge>
  )
}

export function JobDetailTabs({
  activeTab,
  counts,
  overview,
  requirement,
  versions,
  history,
  materials,
  events,
}: JobDetailTabsProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [, startTransition] = useTransition()

  function onTabChange(next: string | number | null) {
    const value = typeof next === "string" ? next : String(next ?? "")
    if (!isJobDetailTab(value) || value === activeTab) {
      return
    }
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", value)
    const query = params.toString()
    startTransition(() => {
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
    })
  }

  return (
    <Tabs
      aria-label="职位详情分区"
      className="min-w-0 gap-6"
      onValueChange={onTabChange}
      value={activeTab}
    >
      <div className="overflow-x-auto">
        <TabsList className="min-w-max" variant="line">
          <TabsTrigger className="gap-2 px-3" value="overview">
            {JOB_DETAIL_TAB_LABELS.overview}
          </TabsTrigger>
          <TabsTrigger className="gap-2 px-3" value="requirement">
            {JOB_DETAIL_TAB_LABELS.requirement}
            <TabCount value={counts?.unsupported} />
          </TabsTrigger>
          <TabsTrigger className="gap-2 px-3" value="versions">
            {JOB_DETAIL_TAB_LABELS.versions}
            <TabCount value={counts?.versions} />
          </TabsTrigger>
          <TabsTrigger className="gap-2 px-3" value="history">
            {JOB_DETAIL_TAB_LABELS.history}
          </TabsTrigger>
          <TabsTrigger className="gap-2 px-3" value="materials">
            {JOB_DETAIL_TAB_LABELS.materials}
            <TabCount value={counts?.materials} />
          </TabsTrigger>
          <TabsTrigger className="gap-2 px-3" value="events">
            {JOB_DETAIL_TAB_LABELS.events}
            <TabCount value={counts?.events} />
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent className="min-w-0 outline-none" value="overview">
        {overview}
      </TabsContent>
      <TabsContent className="min-w-0 outline-none" keepMounted value="requirement">
        {requirement}
      </TabsContent>
      <TabsContent className="min-w-0 outline-none" value="versions">
        {versions}
      </TabsContent>
      <TabsContent className="min-w-0 outline-none" value="history">
        {history}
      </TabsContent>
      <TabsContent className="min-w-0 outline-none" value="materials">
        {materials}
      </TabsContent>
      <TabsContent className="min-w-0 outline-none" value="events">
        {events}
      </TabsContent>
    </Tabs>
  )
}
