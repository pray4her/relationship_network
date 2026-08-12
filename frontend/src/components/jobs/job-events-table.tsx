"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { JOB_DETAIL_EVENTS_PREVIEW_LIMIT } from "@/lib/job-detail-tabs"
import type { JobEventView } from "@/lib/jobs-contract"

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

const eventLabels: Record<string, string> = {
  "job.create": "创建",
  "job.update": "编辑",
  "job.activate": "启用",
  "job.close": "关闭",
  "job.archive": "归档",
  "job.material_upload": "上传材料",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

export function JobEventsTable({ events }: { readonly events: readonly JobEventView[] }) {
  const [expanded, setExpanded] = useState(false)

  if (events.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>暂无操作记录</EmptyTitle>
        </EmptyHeader>
      </Empty>
    )
  }

  const visible =
    expanded || events.length <= JOB_DETAIL_EVENTS_PREVIEW_LIMIT
      ? events
      : events.slice(0, JOB_DETAIL_EVENTS_PREVIEW_LIMIT)
  const hiddenCount = events.length - visible.length

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className={headClassName}>时间</TableHead>
            <TableHead className={headClassName}>动作</TableHead>
            <TableHead className={headClassName}>结果</TableHead>
            <TableHead className={headClassName}>详情</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visible.map((event) => (
            <TableRow key={event.id}>
              <TableCell className="tabular-nums">{formatDateTime(event.created_at)}</TableCell>
              <TableCell>{eventLabels[event.action] ?? event.action}</TableCell>
              <TableCell>{event.result}</TableCell>
              <TableCell>{event.detail || "无补充信息"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {events.length > JOB_DETAIL_EVENTS_PREVIEW_LIMIT ? (
        <div>
          <Button
            onClick={() => setExpanded((current) => !current)}
            size="sm"
            type="button"
            variant="outline"
          >
            {expanded
              ? "只显示最近 20 条"
              : `显示全部 ${events.length.toLocaleString("zh-CN")} 条（还有 ${hiddenCount.toLocaleString("zh-CN")} 条）`}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
