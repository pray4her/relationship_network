"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { toast } from "sonner"

import { copyCurrentRequirementVersionAction } from "@/app/actions/job-requirements"
import { DataRegion, DataRegionContent, DataRegionHeader } from "@/components/layout/page"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type {
  RequirementVersionSummary,
  RequirementWorkspace,
} from "@/lib/job-requirement-contract"

function formatConfirmedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

export function RequirementVersionHistory({
  archived,
  canManage,
  hasEditableDraft,
  jobId,
  versions,
}: {
  readonly archived: boolean
  readonly canManage: boolean
  readonly hasEditableDraft: boolean
  readonly jobId: string
  readonly versions: readonly RequirementVersionSummary[]
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const canCopy = canManage && !archived && versions.some((item) => item.is_current)

  const copyCurrent = () => {
    startTransition(async () => {
      setError(null)
      const result = await copyCurrentRequirementVersionAction(jobId)
      if (result.kind === "ok") {
        toast.success(result.message)
        router.refresh()
        return
      }
      if (result.kind === "error" || result.kind === "revisionConflict") {
        setError(result.message)
      } else {
        setError("服务暂时不可用，请稍后重试。")
      }
    })
  }

  return (
    <DataRegion>
      <DataRegionHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="m-0 text-sm text-muted-foreground">
            确认后的职位需求版本不可修改；修订请复制为新草稿。
          </p>
          {canCopy ? (
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button disabled={pending || hasEditableDraft} type="button" variant="outline" />
                }
              >
                复制为新草稿
              </AlertDialogTrigger>
              <AlertDialogContent size="sm">
                <AlertDialogHeader>
                  <AlertDialogTitle>复制当前职位需求版本？</AlertDialogTitle>
                  <AlertDialogDescription>
                    将创建可编辑草稿，不调用模型。确认后才会生成下一版本。
                    {hasEditableDraft
                      ? "当前已有可编辑草稿，请先完成或放弃后再复制。"
                      : "复制不会改变当前职位需求版本。"}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={pending}>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={copyCurrent} pending={pending}>
                    {pending ? "正在复制…" : "复制为新草稿"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
        </div>
      </DataRegionHeader>
      <DataRegionContent className="flex flex-col gap-3">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>无法复制版本</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {hasEditableDraft && canCopy ? (
          <Alert>
            <AlertTitle>已有可编辑草稿</AlertTitle>
            <AlertDescription>请先完成或放弃当前草稿，再复制版本。</AlertDescription>
          </Alert>
        ) : null}
        {versions.length === 0 ? (
          <p className="text-sm text-muted-foreground">尚无确认的职位需求版本。</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>Schema</TableHead>
                <TableHead>确认时间</TableHead>
                <TableHead>来源版本</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((version) => (
                <TableRow key={version.id}>
                  <TableCell className="font-medium tabular-nums">
                    v{version.version_number}
                    {version.is_current ? (
                      <Badge className="ml-2" variant="secondary">
                        当前
                      </Badge>
                    ) : null}
                  </TableCell>
                  <TableCell className="font-mono text-xs" translate="no">
                    {version.requirement_schema_version_id}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatConfirmedAt(version.confirmed_at)}
                  </TableCell>
                  <TableCell className="tabular-nums text-muted-foreground">
                    {version.source_version_id === null ? "—" : "已引用"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataRegionContent>
    </DataRegion>
  )
}

export function RequirementMatchingGateAlert({
  workspace,
}: {
  readonly workspace: RequirementWorkspace
}) {
  if (!workspace.matching_blocked) return null
  return (
    <Alert>
      <AlertTitle>历史启用职位待确认需求</AlertTitle>
      <AlertDescription>
        该职位继续占用活跃职位额度，但在确认首个职位需求版本前不能用于匹配。
      </AlertDescription>
    </Alert>
  )
}
