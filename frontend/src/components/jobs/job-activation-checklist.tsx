import Link from "next/link"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { JobDetailTab } from "@/lib/job-detail-tabs"
import { cn } from "@/lib/utils"

export type JobActivationChecklistItem = {
  readonly id: string
  readonly label: string
  readonly done: boolean
  readonly tab: JobDetailTab
  readonly hint?: string
}

export function buildJobActivationChecklistItems(input: {
  readonly hasConfirmedVersion: boolean
  readonly matchingBlocked: boolean
  readonly materialCount: number
}): readonly JobActivationChecklistItem[] {
  return [
    {
      id: "confirmed-version",
      label: "已确认职位需求版本",
      done: input.hasConfirmedVersion,
      tab: "versions",
      hint: input.hasConfirmedVersion
        ? "可用于后续匹配流程。"
        : "请在需求草稿中确认版本，或从版本页复制后修订。",
    },
    {
      id: "matching-gate",
      label: "匹配门禁已解除",
      done: !input.matchingBlocked,
      tab: "requirement",
      hint: input.matchingBlocked
        ? "历史启用职位在确认首个需求版本前不能用于匹配。"
        : "当前不因需求门禁阻塞匹配。",
    },
    {
      id: "materials",
      label: "已上传职位材料",
      done: input.materialCount > 0,
      tab: "materials",
      hint:
        input.materialCount > 0
          ? `当前 ${input.materialCount.toLocaleString("zh-CN")} 份材料（信息提示，不阻止启用）。`
          : "可选：上传材料便于生成更完整的需求草稿。",
    },
  ]
}

type JobActivationChecklistProps = {
  readonly jobId: string
  readonly items: readonly JobActivationChecklistItem[]
  readonly className?: string
}

export function JobActivationChecklist({ jobId, items, className }: JobActivationChecklistProps) {
  if (items.length === 0) {
    return null
  }

  const pending = items.filter((item) => !item.done)
  const title =
    pending.length === 0 ? "启用前检查已完成" : `启用前检查 · 还有 ${pending.length} 项待处理`

  return (
    <Alert className={cn(className)} aria-labelledby="job-activation-checklist-heading">
      <AlertTitle id="job-activation-checklist-heading">{title}</AlertTitle>
      <AlertDescription>
        <ul className="m-0 mt-2 flex list-none flex-col gap-3 p-0">
          {items.map((item) => (
            <li className="flex min-w-0 flex-col gap-1" key={item.id}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={item.done ? "success" : "outline"}>
                  {item.done ? "已完成" : "待处理"}
                </Badge>
                <Button
                  className="h-auto px-0"
                  render={<Link href={`/jobs/${jobId}?tab=${item.tab}`} />}
                  size="sm"
                  variant="link"
                >
                  {item.label}
                </Button>
              </div>
              {item.hint ? <p className="m-0 text-sm text-muted-foreground">{item.hint}</p> : null}
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  )
}
