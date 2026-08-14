import {
  DataRegion,
  DataRegionContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
} from "@/components/layout/page"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/format"
import type {
  HistoryDraft,
  RequirementHistory,
  RequirementTaskStatus,
} from "@/lib/job-requirement-contract"

const taskStatusLabels: Readonly<Record<RequirementTaskStatus, string>> = {
  queued: "排队中",
  running: "生成中",
  retry_scheduled: "等待重试",
  cancel_requested: "正在取消",
  succeeded: "生成成功",
  failed: "生成失败",
  cancelled: "已取消",
}

const draftStatusLabels: Readonly<Record<HistoryDraft["status"], string>> = {
  editable: "编辑中",
  confirmed: "已确认",
  replaced: "已替换",
  abandoned: "已放弃",
}

const sourceKindLabels: Readonly<Record<string, string>> = {
  "job-description": "职位描述",
  "job-material": "职位材料",
}

function TaskStatusBadge({ status }: { readonly status: RequirementTaskStatus }) {
  const variant =
    status === "succeeded"
      ? "success"
      : status === "failed" || status === "cancelled"
        ? "destructive"
        : status === "retry_scheduled" || status === "cancel_requested"
          ? "warning"
          : "secondary"
  return <Badge variant={variant}>{taskStatusLabels[status]}</Badge>
}

function HistorySection({
  empty,
  emptyText,
  headingId,
  title,
  children,
}: {
  readonly empty: boolean
  readonly emptyText: string
  readonly headingId: string
  readonly title: string
  readonly children: React.ReactNode
}) {
  return (
    <PageSection aria-labelledby={headingId}>
      <PageSectionHeader>
        <PageSectionHeaderContent>
          <PageSectionTitle id={headingId}>{title}</PageSectionTitle>
        </PageSectionHeaderContent>
      </PageSectionHeader>
      <DataRegion>
        <DataRegionContent className={empty ? "px-5 py-4" : undefined}>
          {empty ? <p className="m-0 text-sm text-muted-foreground">{emptyText}</p> : children}
        </DataRegionContent>
      </DataRegion>
    </PageSection>
  )
}

export function RequirementHistoryView({ history }: { readonly history: RequirementHistory }) {
  return (
    <div className="flex min-w-0 flex-col gap-8">
      <HistorySection
        empty={history.tasks.length === 0}
        emptyText="尚无解析任务记录。"
        headingId="history-tasks-heading"
        title="解析任务"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>状态</TableHead>
              <TableHead>错误码</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead>完成时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.tasks.map((task) => (
              <TableRow key={task.id}>
                <TableCell>
                  <TaskStatusBadge status={task.status} />
                </TableCell>
                <TableCell className="font-mono text-xs" translate="no">
                  {task.error_code ?? "—"}
                </TableCell>
                <TableCell className="tabular-nums">{formatDateTime(task.created_at)}</TableCell>
                <TableCell className="tabular-nums">
                  {task.completed_at === null ? "—" : formatDateTime(task.completed_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </HistorySection>

      <HistorySection
        empty={history.drafts.length === 0}
        emptyText="尚无草稿记录。"
        headingId="history-drafts-heading"
        title="草稿"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>状态</TableHead>
              <TableHead>Schema</TableHead>
              <TableHead numeric>修订</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead>更新时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.drafts.map((draft) => (
              <TableRow key={draft.id}>
                <TableCell>
                  <Badge variant={draft.status === "confirmed" ? "success" : "secondary"}>
                    {draftStatusLabels[draft.status]}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs" translate="no">
                  {draft.requirement_schema_version_id}
                </TableCell>
                <TableCell numeric>{draft.revision.toLocaleString("zh-CN")}</TableCell>
                <TableCell className="tabular-nums">{formatDateTime(draft.created_at)}</TableCell>
                <TableCell className="tabular-nums">{formatDateTime(draft.updated_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </HistorySection>

      <HistorySection
        empty={history.versions.length === 0}
        emptyText="尚无确认的职位需求版本。"
        headingId="history-versions-heading"
        title="版本"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>版本</TableHead>
              <TableHead>Schema</TableHead>
              <TableHead>确认时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.versions.map((version) => (
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
                  {formatDateTime(version.confirmed_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </HistorySection>

      <HistorySection
        empty={history.schema_upgrades.length === 0}
        emptyText="尚无 Schema 升级记录。"
        headingId="history-upgrades-heading"
        title="Schema 升级"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Schema</TableHead>
              <TableHead>转换器</TableHead>
              <TableHead>逐项映射</TableHead>
              <TableHead>未解决项</TableHead>
              <TableHead>升级时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.schema_upgrades.map((upgrade) => {
              const losslessCount = upgrade.item_mappings.filter((item) => item.lossless).length
              const lossyCount = upgrade.item_mappings.length - losslessCount
              const unresolvedCount = upgrade.lossy_resolutions.filter(
                (entry) => entry.resolution === null,
              ).length
              return (
                <TableRow key={upgrade.id}>
                  <TableCell className="font-mono text-xs" translate="no">
                    {upgrade.from_schema_version_id} → {upgrade.to_schema_version_id}
                  </TableCell>
                  <TableCell className="font-mono text-xs" translate="no">
                    {upgrade.converter_version}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    无损 {losslessCount.toLocaleString("zh-CN")} · 有损{" "}
                    {lossyCount.toLocaleString("zh-CN")}
                  </TableCell>
                  <TableCell>
                    {upgrade.lossy_resolutions.length === 0 ? (
                      "—"
                    ) : unresolvedCount > 0 ? (
                      <Badge variant="warning">
                        {unresolvedCount.toLocaleString("zh-CN")} 项待解决
                      </Badge>
                    ) : (
                      <Badge variant="success">已全部解决</Badge>
                    )}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatDateTime(upgrade.created_at)}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </HistorySection>

      <HistorySection
        empty={history.sources.length === 0}
        emptyText="尚无来源快照记录。"
        headingId="history-sources-heading"
        title="来源快照"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>来源</TableHead>
              <TableHead>类型</TableHead>
              <TableHead numeric>字符数</TableHead>
              <TableHead>校验和</TableHead>
              <TableHead>正文</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.sources.map((source) => (
              <TableRow key={`${source.snapshot_id}:${source.source_id}`}>
                <TableCell className="font-mono text-xs" translate="no">
                  {source.source_id}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {sourceKindLabels[source.source_kind] ?? source.source_kind}
                  </Badge>
                </TableCell>
                <TableCell numeric>{source.unicode_characters.toLocaleString("zh-CN")}</TableCell>
                <TableCell className="font-mono text-xs" translate="no">
                  {source.sent_sha256.slice(0, 12)}…
                </TableCell>
                <TableCell>
                  {source.body_purged_at === null ? (
                    <Badge variant="success">正文保留</Badge>
                  ) : (
                    <span className="inline-flex flex-wrap items-center gap-2">
                      <Badge variant="warning">正文已清理</Badge>
                      <span className="text-muted-foreground text-xs tabular-nums">
                        {formatDateTime(source.body_purged_at)}
                      </span>
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </HistorySection>

      <HistorySection
        empty={history.change_events.length === 0}
        emptyText="尚无变更记录。"
        headingId="history-events-heading"
        title="变更记录"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>操作</TableHead>
              <TableHead>结果</TableHead>
              <TableHead>详情</TableHead>
              <TableHead>时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.change_events.map((event) => (
              <TableRow key={event.id}>
                <TableCell className="font-mono text-xs" translate="no">
                  {event.action}
                </TableCell>
                <TableCell>
                  <Badge variant={event.result === "success" ? "success" : "destructive"}>
                    {event.result === "success" ? "成功" : "失败"}
                  </Badge>
                </TableCell>
                <TableCell className="max-w-md break-words text-muted-foreground">
                  {event.detail || "—"}
                </TableCell>
                <TableCell className="tabular-nums">{formatDateTime(event.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </HistorySection>
    </div>
  )
}
