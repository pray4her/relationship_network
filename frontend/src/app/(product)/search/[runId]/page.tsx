import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import {
  DataRegion,
  DataRegionContent,
  DataRegionFooter,
  DataRegionHeader,
  Page,
  PageActions,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionDescription,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { SearchHitsTable } from "@/components/search/search-hits-table"
import { SearchInterpretationCard } from "@/components/search/search-interpretation-card"
import { StatusBadge, type StatusMeta } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { formatDateTime } from "@/lib/format"
import { databaseUuidSchema } from "@/lib/llm-configuration-contract"
import { createSearchTransport, loadSearchRun } from "@/lib/search-client"
import type { SearchRunFailureReason, SearchRunStatus } from "@/lib/search-contract"

export const metadata: Metadata = {
  title: "搜索结果",
}

const statusMeta: Readonly<Record<SearchRunStatus, StatusMeta>> = {
  in_progress: { label: "执行中", tone: "warning" },
  succeeded: { label: "成功", tone: "success" },
  failed: { label: "失败", tone: "destructive" },
}

const failureReasonLabels: Readonly<Record<SearchRunFailureReason, string>> = {
  interpretation_invalid: "搜索解释无效：未能从原句解析出可执行的硬条件或研究主题。",
  interpretation_error: "搜索解释失败：模型调用失败或超时，未扣减额度。",
  search_base_error: "检索底座失败：可重新发起一次新的搜索。",
  search_base_timeout: "检索底座超时：可重新发起一次新的搜索。",
  quota_exceeded: "本计费周期搜索额度已用完，无法发起新的搜索。",
}

function Notice({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>搜索结果</PageTitle>
          <PageDescription>查看一次自然语言搜索的冻结解释与命中快照。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

type SearchRunDetailPageProps = {
  readonly params: Promise<{ readonly runId: string }>
  readonly searchParams: Promise<{ readonly sort?: string; readonly cursor?: string }>
}

export default async function SearchRunDetailPage({
  params,
  searchParams,
}: SearchRunDetailPageProps) {
  const { runId } = await params
  if (!databaseUuidSchema.safeParse(runId).success) notFound()

  const { sort, cursor } = await searchParams

  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return (
      <Notice>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
          登录
        </Link>
        。
      </Notice>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") return <Notice>登录状态无效，请重新登录。</Notice>

  const result = await loadSearchRun(
    createSearchTransport(),
    session,
    runId,
    sort ?? null,
    cursor ?? null,
  )
  if (result.kind === "mfaRequired") redirect("/settings/security")
  if (result.kind === "anonymous") redirect("/login")
  if (result.kind === "notFound") notFound()
  if (result.kind !== "ok") return <Notice>搜索结果暂时不可用，请稍后再试。</Notice>

  const { run, hits, next_cursor, total, sorted_by, left_relevance_order } = result.detail

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle id="search-run-heading">{run.utterance}</PageTitle>
          <PageDescription>提交于 {formatDateTime(run.created_at)}</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <StatusBadge {...statusMeta[run.status]} />
        </PageActions>
      </PageHeader>

      {run.status === "failed" ? (
        <Alert variant="destructive">
          <AlertDescription>
            {run.failure_reason ? failureReasonLabels[run.failure_reason] : "搜索失败。"}
          </AlertDescription>
        </Alert>
      ) : null}

      {run.status === "succeeded" ? (
        <>
          <PageSection aria-labelledby="interpretation-heading">
            <PageSectionHeader>
              <PageSectionHeaderContent>
                <PageSectionTitle id="interpretation-heading">搜索解释</PageSectionTitle>
              </PageSectionHeaderContent>
            </PageSectionHeader>
            <SearchInterpretationCard interpretation={run.search_interpretation} />
          </PageSection>

          <PageSection aria-labelledby="hits-heading">
            <PageSectionHeader>
              <PageSectionHeaderContent>
                <PageSectionTitle id="hits-heading">命中结果</PageSectionTitle>
                <PageSectionDescription>
                  共 {total} 条命中；数据版本 {run.data_version ?? "—"}。
                </PageSectionDescription>
              </PageSectionHeaderContent>
            </PageSectionHeader>
            <DataRegion>
              <DataRegionHeader>点击姓名进入本地人才详情，联系方式始终脱敏。</DataRegionHeader>
              <DataRegionContent>
                {hits.length === 0 ? (
                  <p className="py-6 text-sm text-muted-foreground">本次搜索没有命中。</p>
                ) : (
                  <SearchHitsTable
                    hits={hits}
                    sort={sorted_by}
                    hasResearchTopic={run.has_research_topic}
                    leftRelevanceOrder={left_relevance_order}
                  />
                )}
              </DataRegionContent>
              {next_cursor ? (
                <DataRegionFooter>
                  <Link
                    className="text-sm underline underline-offset-4"
                    href={{ query: { cursor: next_cursor, sort: sorted_by } }}
                  >
                    下一页
                  </Link>
                </DataRegionFooter>
              ) : null}
            </DataRegion>
          </PageSection>
        </>
      ) : null}
    </Page>
  )
}
