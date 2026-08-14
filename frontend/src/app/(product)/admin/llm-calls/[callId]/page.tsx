import { ArrowLeftIcon } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import {
  LlmCallMetadataStatusBadge,
  LlmCallOutcomeBadge,
} from "@/components/admin/admin-status-badges"
import { LlmRawResponseDialog } from "@/components/admin/llm-raw-response-dialog"
import {
  DataRegion,
  DataRegionContent,
  DataRegionHeader,
  DescriptionDetails,
  DescriptionItem,
  DescriptionList,
  DescriptionTerm,
  Page,
  PageActions,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionDescription,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { Button } from "@/components/ui/button"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime } from "@/lib/format"
import { createLlmCallTransport, loadLlmCallDetail } from "@/lib/llm-call-client"
import {
  displayValue,
  formatDiagnosticCost,
  llmCallScopeLabels,
  llmCallTypeLabels,
} from "@/lib/llm-call-view"
import { databaseUuidSchema } from "@/lib/llm-configuration-contract"

export const metadata: Metadata = { title: "LLM 调用详情" }

type LlmCallDetailPageProps = {
  readonly params: Promise<{ readonly callId: string }>
}

function JsonFact({ value }: { readonly value: Record<string, unknown> }) {
  return (
    <pre className="m-0 max-h-80 overflow-auto rounded-md border border-border bg-muted p-4 whitespace-pre-wrap break-words font-mono text-sm leading-relaxed">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export default async function LlmCallDetailPage({ params }: LlmCallDetailPageProps) {
  const { callId } = await params
  if (!databaseUuidSchema.safeParse(callId).success) notFound()
  const guard = await requireAdminView()
  if (guard.kind !== "ok") {
    return <AdminGateNotice failure={guard.kind} title="LLM 调用详情" />
  }
  const result = await loadLlmCallDetail(createLlmCallTransport(), guard.session, callId)
  if (result.kind === "mfaRequired") redirect("/settings/security")
  if (result.kind === "notFound") notFound()
  if (result.kind === "anonymous" || result.kind === "forbidden") {
    return <AdminGateNotice failure={result.kind} title="LLM 调用详情" />
  }
  if (result.kind !== "ok") {
    return (
      <AdminGateNotice
        failure="unreachable"
        message="调用详情暂时不可用，请稍后重试。"
        title="LLM 调用详情"
      />
    )
  }

  const { call, metadata_events: metadataEvents, outcomes } = result.detail
  const timeline = [
    ...outcomes.map((event) => ({ createdAt: event.created_at, event, kind: "outcome" as const })),
    ...metadataEvents.map((event) => ({
      createdAt: event.created_at,
      event,
      kind: "metadata" as const,
    })),
  ].sort((left, right) => Date.parse(left.createdAt) - Date.parse(right.createdAt))

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理 / AI 基础设施 / 调用详情</PageEyebrow>
          <PageTitle>LLM 调用详情</PageTitle>
          <PageDescription className="break-all font-mono text-sm">{call.id}</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Button render={<Link href="/admin/llm-calls" />} variant="secondary">
            <ArrowLeftIcon /> 返回调用记录
          </Button>
          <LlmRawResponseDialog available={result.detail.raw_response_available} callId={call.id} />
        </PageActions>
      </PageHeader>

      <PageSection aria-labelledby="request-facts-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="request-facts-heading">请求事实</PageSectionTitle>
            <PageSectionDescription>
              核心记录在请求发出前独立提交，后续仅追加事件。
            </PageSectionDescription>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DescriptionList>
          <DescriptionItem>
            <DescriptionTerm>调用范围</DescriptionTerm>
            <DescriptionDetails>{llmCallScopeLabels[call.scope]}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>调用类型</DescriptionTerm>
            <DescriptionDetails>{llmCallTypeLabels[call.call_type]}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>模型</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {call.model}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>请求序号</DescriptionTerm>
            <DescriptionDetails className="font-mono tabular-nums">
              #{call.request_number}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>创建时间</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {formatDateTime(call.created_at)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>租户 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {displayValue(call.tenant_id)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>配置尝试 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {displayValue(call.platform_attempt_id)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>关联调用 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {displayValue(call.correlation_call_id)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>配置版本 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {displayValue(call.configuration_version_id)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>输入快照 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {displayValue(call.input_snapshot_id)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>输入长度</DescriptionTerm>
            <DescriptionDetails className="font-mono tabular-nums">
              {call.input_length}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>原始响应到期</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {result.detail.raw_response_expires_at
                ? formatDateTime(result.detail.raw_response_expires_at)
                : "—"}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem className="md:col-span-2">
            <DescriptionTerm>提示词版本 / SHA-256</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {call.prompt_version_id}
              <br />
              {call.prompt_sha256}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem className="md:col-span-2">
            <DescriptionTerm>Schema 版本 / SHA-256</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {call.requirement_schema_version_id}
              <br />
              {call.requirement_schema_sha256}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem className="md:col-span-2">
            <DescriptionTerm>输入 / 请求 SHA-256</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {call.input_sha256}
              <br />
              {call.request_hash}
            </DescriptionDetails>
          </DescriptionItem>
        </DescriptionList>
        <div className="grid grid-cols-2 gap-6 max-lg:grid-cols-1">
          <div className="flex min-w-0 flex-col gap-2">
            <h3 className="m-0 text-base font-medium">输入来源摘要</h3>
            <JsonFact value={call.input_sources_summary} />
          </div>
          <div className="flex min-w-0 flex-col gap-2">
            <h3 className="m-0 text-base font-medium">生成参数</h3>
            <JsonFact value={call.parameters} />
          </div>
        </div>
      </PageSection>

      <PageSection aria-labelledby="event-timeline-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="event-timeline-heading">结果与元数据时间线</PageSectionTitle>
            <PageSectionDescription>
              事件按写入时间排列；元数据补齐不会改写业务结果。
            </PageSectionDescription>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionHeader>
            <p className="m-0 font-medium">{timeline.length} 个只增事件</p>
          </DataRegionHeader>
          <DataRegionContent>
            {timeline.length === 0 ? (
              <p className="m-0 p-6 text-muted-foreground">尚未记录结果或元数据事件。</p>
            ) : (
              <ol className="m-0 list-none divide-y divide-border p-0">
                {timeline.map((item) => (
                  <li
                    className="grid grid-cols-[12rem_minmax(0,1fr)] gap-6 p-5 max-md:grid-cols-1 max-md:gap-2"
                    key={`${item.kind}-${item.event.sequence_number}`}
                  >
                    <time
                      className="font-mono text-sm text-muted-foreground tabular-nums"
                      dateTime={item.createdAt}
                    >
                      {formatDateTime(item.createdAt)}
                    </time>
                    {item.kind === "outcome" ? (
                      <div className="flex min-w-0 flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <LlmCallOutcomeBadge outcome={item.event.outcome} />
                          <span className="font-mono text-sm">
                            结果事件 #{item.event.sequence_number}
                          </span>
                        </div>
                        <p className="m-0 break-words text-sm text-muted-foreground">
                          分类：{item.event.category} · HTTP：{displayValue(item.event.http_status)}{" "}
                          · 耗时：
                          {item.event.duration_ms === null ? "—" : `${item.event.duration_ms} ms`}
                        </p>
                        <p className="m-0 break-all font-mono text-sm text-muted-foreground">
                          generation/request ID：{displayValue(item.event.provider_request_id)}
                        </p>
                      </div>
                    ) : (
                      <div className="flex min-w-0 flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <LlmCallMetadataStatusBadge status={item.event.status} />
                          <span className="font-mono text-sm">
                            元数据事件 #{item.event.sequence_number}
                          </span>
                        </div>
                        <p className="m-0 break-words text-sm text-muted-foreground">
                          来源：{item.event.source} · Token：{displayValue(item.event.total_tokens)}{" "}
                          · 成本：{formatDiagnosticCost(item.event.cost)}
                        </p>
                        <p className="m-0 break-all font-mono text-sm text-muted-foreground">
                          generation ID：{displayValue(item.event.generation_id)}
                        </p>
                        {item.event.next_retry_at !== null && (
                          <p className="m-0 text-sm text-muted-foreground tabular-nums">
                            下次重试：{formatDateTime(item.event.next_retry_at)}
                          </p>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
