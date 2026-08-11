import { ActivityIcon, SearchXIcon } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import {
  DataRegion,
  DataRegionContent,
  DataRegionFooter,
  DataRegionHeader,
  Page,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageTitle,
  PageToolbar,
} from "@/components/layout/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { requireAdminView } from "@/lib/admin-guard"
import { createLlmCallTransport, loadLlmCalls } from "@/lib/llm-call-client"
import {
  llmCallMetadataStatusSchema,
  llmCallOutcomeSchema,
  llmCallScopeSchema,
  llmCallTypeSchema,
} from "@/lib/llm-call-contract"
import {
  formatDiagnosticDateTime,
  llmCallMetadataStatusLabels,
  llmCallOutcomeLabels,
  llmCallScopeLabels,
  llmCallTypeLabels,
} from "@/lib/llm-call-view"

export const metadata: Metadata = { title: "LLM 调用记录" }

type SearchParameters = Record<string, string | string[] | undefined>
type LlmCallListPageProps = { readonly searchParams: Promise<SearchParameters> }

const selectClassName =
  "h-[var(--control-height)] w-full min-w-0 rounded-[var(--radius-md)] border border-input bg-background px-[var(--button-padding-inline-sm)] text-sm outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)]"

function first(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : ""
}

function dateBoundary(value: string, end: boolean): string | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined
  return `${value}T${end ? "23:59:59.999" : "00:00:00.000"}Z`
}

function cleanQuery(parameters: SearchParameters): Record<string, string> {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(parameters)) {
    const item = first(value)
    if (item !== "" && key !== "cursor") query[key] = item
  }
  return query
}

function OutcomeBadge({ outcome }: { readonly outcome: string | null }) {
  if (outcome === null) return <Badge variant="neutral">等待结果</Badge>
  const parsed = llmCallOutcomeSchema.safeParse(outcome)
  if (!parsed.success) return <Badge variant="neutral">未知</Badge>
  const variant =
    parsed.data === "succeeded" ? "success" : parsed.data === "failed" ? "destructive" : "warning"
  return <Badge variant={variant}>{llmCallOutcomeLabels[parsed.data]}</Badge>
}

function MetadataBadge({ status }: { readonly status: string | null }) {
  if (status === null) return <Badge variant="neutral">等待元数据</Badge>
  const parsed = llmCallMetadataStatusSchema.safeParse(status)
  if (!parsed.success) return <Badge variant="neutral">未知</Badge>
  const variant =
    parsed.data === "available" ? "success" : parsed.data === "retry_scheduled" ? "info" : "warning"
  return <Badge variant={variant}>{llmCallMetadataStatusLabels[parsed.data]}</Badge>
}

export default async function LlmCallListPage({ searchParams }: LlmCallListPageProps) {
  const parameters = await searchParams
  const rawScope = first(parameters["scope"])
  const rawCallType = first(parameters["call_type"])
  const rawOutcome = first(parameters["outcome"])
  const rawMetadataStatus = first(parameters["metadata_status"])
  const scope = llmCallScopeSchema.safeParse(rawScope)
  const callType = llmCallTypeSchema.safeParse(rawCallType)
  const outcome = llmCallOutcomeSchema.safeParse(rawOutcome)
  const metadataStatus = llmCallMetadataStatusSchema.safeParse(rawMetadataStatus)
  const tenantId = first(parameters["tenant_id"])
  const platformAttemptId = first(parameters["platform_attempt_id"])
  const createdFrom = first(parameters["created_from"])
  const createdTo = first(parameters["created_to"])
  const cursor = first(parameters["cursor"])

  const guard = await requireAdminView()
  if (guard.kind !== "ok") {
    return <AdminGateNotice failure={guard.kind} title="LLM 调用记录" />
  }
  const fromBoundary = dateBoundary(createdFrom, false)
  const toBoundary = dateBoundary(createdTo, true)
  const result = await loadLlmCalls(createLlmCallTransport(), guard.session, {
    ...(callType.success ? { callType: callType.data } : {}),
    ...(fromBoundary ? { createdFrom: fromBoundary } : {}),
    ...(toBoundary ? { createdTo: toBoundary } : {}),
    ...(cursor ? { cursor } : {}),
    ...(metadataStatus.success ? { metadataStatus: metadataStatus.data } : {}),
    ...(outcome.success ? { outcome: outcome.data } : {}),
    ...(platformAttemptId ? { platformAttemptId } : {}),
    ...(scope.success ? { scope: scope.data } : {}),
    ...(tenantId ? { tenantId } : {}),
  })
  if (result.kind === "mfaRequired") redirect("/settings/security")
  if (result.kind === "anonymous" || result.kind === "forbidden") {
    return <AdminGateNotice failure={result.kind} title="LLM 调用记录" />
  }

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理 / AI 基础设施</PageEyebrow>
          <PageTitle>LLM 调用记录</PageTitle>
          <PageDescription>
            检查每次外部请求的范围、结果、延迟元数据和原始响应保留状态。请求正文与提示词正文不会写入调用记录。
          </PageDescription>
        </PageHeaderContent>
      </PageHeader>

      <PageSection aria-labelledby="llm-call-list-heading">
        <h2 className="sr-only" id="llm-call-list-heading">
          调用记录筛选与结果
        </h2>
        <PageToolbar render={<form action="/admin/llm-calls" method="get" />}>
          <Field className="w-36">
            <FieldLabel htmlFor="llm-call-scope">调用范围</FieldLabel>
            <select
              className={selectClassName}
              defaultValue={scope.success ? scope.data : ""}
              id="llm-call-scope"
              name="scope"
            >
              <option value="">全部范围</option>
              <option value="platform">平台</option>
              <option value="tenant">租户</option>
            </select>
          </Field>
          <Field className="w-44">
            <FieldLabel htmlFor="llm-call-type">调用类型</FieldLabel>
            <select
              className={selectClassName}
              defaultValue={callType.success ? callType.data : ""}
              id="llm-call-type"
              name="call_type"
            >
              <option value="">全部类型</option>
              <option value="config_probe">配置探测</option>
              <option value="job_requirement_parsing">职位需求解析</option>
            </select>
          </Field>
          <Field className="w-36">
            <FieldLabel htmlFor="llm-call-outcome">调用结果</FieldLabel>
            <select
              className={selectClassName}
              defaultValue={outcome.success ? outcome.data : ""}
              id="llm-call-outcome"
              name="outcome"
            >
              <option value="">全部结果</option>
              {llmCallOutcomeSchema.options.map((item) => (
                <option key={item} value={item}>
                  {llmCallOutcomeLabels[item]}
                </option>
              ))}
            </select>
          </Field>
          <Field className="w-36">
            <FieldLabel htmlFor="llm-call-metadata">元数据</FieldLabel>
            <select
              className={selectClassName}
              defaultValue={metadataStatus.success ? metadataStatus.data : ""}
              id="llm-call-metadata"
              name="metadata_status"
            >
              <option value="">全部状态</option>
              {llmCallMetadataStatusSchema.options.map((item) => (
                <option key={item} value={item}>
                  {llmCallMetadataStatusLabels[item]}
                </option>
              ))}
            </select>
          </Field>
          <Field className="min-w-64 flex-1">
            <FieldLabel htmlFor="llm-call-tenant-id">租户 ID</FieldLabel>
            <Input
              defaultValue={tenantId}
              id="llm-call-tenant-id"
              name="tenant_id"
              placeholder="UUID"
            />
          </Field>
          <Field className="min-w-64 flex-1">
            <FieldLabel htmlFor="llm-call-attempt-id">配置尝试 ID</FieldLabel>
            <Input
              defaultValue={platformAttemptId}
              id="llm-call-attempt-id"
              name="platform_attempt_id"
              placeholder="UUID"
            />
          </Field>
          <Field className="w-44">
            <FieldLabel htmlFor="llm-call-from">开始日期</FieldLabel>
            <Input defaultValue={createdFrom} id="llm-call-from" name="created_from" type="date" />
          </Field>
          <Field className="w-44">
            <FieldLabel htmlFor="llm-call-to">结束日期</FieldLabel>
            <Input defaultValue={createdTo} id="llm-call-to" name="created_to" type="date" />
          </Field>
          <Button type="submit" variant="secondary">
            筛选
          </Button>
          <Button render={<Link href="/admin/llm-calls" />} variant="ghost">
            清除
          </Button>
        </PageToolbar>

        {result.kind !== "ok" ? (
          <Alert variant="destructive">
            <AlertDescription>调用记录暂时不可用。请检查筛选值或稍后重试。</AlertDescription>
          </Alert>
        ) : (
          <DataRegion>
            <DataRegionHeader>
              <div>
                <p className="m-0 font-medium text-foreground">最近调用</p>
                <p className="m-0 text-sm text-muted-foreground">
                  本页最多显示 50 条，按创建时间倒序。
                </p>
              </div>
              <Badge variant="neutral">{result.page.calls.length} 条</Badge>
            </DataRegionHeader>
            <DataRegionContent>
              {result.page.calls.length === 0 ? (
                <Empty variant="no-results">
                  <EmptyMedia>
                    <SearchXIcon />
                  </EmptyMedia>
                  <EmptyHeader>
                    <EmptyTitle>没有符合条件的调用</EmptyTitle>
                    <EmptyDescription>调整筛选条件后再试。</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <Table className="min-w-[72rem]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>创建时间</TableHead>
                      <TableHead>范围 / 类型</TableHead>
                      <TableHead>模型</TableHead>
                      <TableHead>请求</TableHead>
                      <TableHead>结果</TableHead>
                      <TableHead>元数据</TableHead>
                      <TableHead>原始响应</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.page.calls.map((call) => (
                      <TableRow key={call.id}>
                        <TableCell className="whitespace-nowrap tabular-nums">
                          <Link
                            className="font-medium text-primary underline underline-offset-4"
                            href={`/admin/llm-calls/${call.id}`}
                          >
                            {formatDiagnosticDateTime(call.created_at)}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <span className="block">{llmCallScopeLabels[call.scope]}</span>
                          <span className="text-sm text-muted-foreground">
                            {llmCallTypeLabels[call.call_type]}
                          </span>
                        </TableCell>
                        <TableCell className="max-w-72 break-all font-mono text-sm">
                          {call.model}
                        </TableCell>
                        <TableCell className="font-mono tabular-nums">
                          #{call.request_number}
                        </TableCell>
                        <TableCell>
                          <OutcomeBadge outcome={call.outcome} />
                        </TableCell>
                        <TableCell>
                          <MetadataBadge status={call.metadata_status} />
                        </TableCell>
                        <TableCell>
                          <Badge variant={call.raw_response_available ? "info" : "neutral"}>
                            {call.raw_response_available ? "可查看" : "不可用"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </DataRegionContent>
            {result.page.next_cursor !== null && (
              <DataRegionFooter className="flex justify-end">
                <Button
                  render={
                    <Link
                      href={{
                        pathname: "/admin/llm-calls",
                        query: { ...cleanQuery(parameters), cursor: result.page.next_cursor },
                      }}
                    />
                  }
                  variant="secondary"
                >
                  下一页
                </Button>
              </DataRegionFooter>
            )}
          </DataRegion>
        )}
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <ActivityIcon aria-hidden="true" className="size-4" />
          延迟元数据补齐只更新诊断事实，不会改变配置启用结果。
        </p>
      </PageSection>
    </Page>
  )
}
