import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import {
  DataRegion,
  DataRegionContent,
  DataRegionFooter,
  DataRegionHeader,
  Page,
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
import { SearchUtteranceForm } from "@/components/search/search-utterance-form"
import { StatusBadge, type StatusMeta } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { formatDateTime } from "@/lib/format"
import { createSearchTransport, loadSearchRuns } from "@/lib/search-client"
import type { SearchRunFailureReason, SearchRunStatus, SearchRunView } from "@/lib/search-contract"

export const metadata: Metadata = {
  title: "自然语言搜索",
}

const statusMeta: Readonly<Record<SearchRunStatus, StatusMeta>> = {
  in_progress: { label: "执行中", tone: "warning" },
  succeeded: { label: "成功", tone: "success" },
  failed: { label: "失败", tone: "destructive" },
}

const failureReasonLabels: Readonly<Record<SearchRunFailureReason, string>> = {
  interpretation_invalid: "搜索解释无效",
  interpretation_error: "搜索解释失败",
  search_base_error: "检索底座失败",
  search_base_timeout: "检索底座超时",
  quota_exceeded: "额度不足",
}

function Notice({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>自然语言搜索</PageTitle>
          <PageDescription>用自然语言检索人才，并单独计量搜索额度。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

type SearchPageProps = {
  readonly searchParams: Promise<{ readonly cursor?: string }>
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const { cursor } = await searchParams

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

  const permissions = auth.view.permissions
  const canRun = permissions.includes("search:run")
  const canRead = permissions.includes("search:read")
  if (!canRun && !canRead) {
    return <Notice>你没有访问自然语言搜索的权限。</Notice>
  }

  let runs: SearchRunView[] = []
  let next_cursor: string | null = null
  if (canRead) {
    const list = await loadSearchRuns(createSearchTransport(), session, cursor ?? null)
    if (list.kind === "mfaRequired") redirect("/settings/security")
    if (list.kind === "anonymous") redirect("/login")
    if (list.kind === "unreachable") return <Notice>搜索服务暂时不可用，请稍后再试。</Notice>
    if (list.kind === "ok") {
      runs = [...list.list.runs]
      next_cursor = list.list.next_cursor
    }
  }

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>自然语言搜索</PageTitle>
          <PageDescription>用自然语言检索人才，提交后立即执行并计 1 次搜索额度。</PageDescription>
        </PageHeaderContent>
      </PageHeader>

      {canRun ? (
        <PageSection aria-labelledby="new-search-heading">
          <PageSectionHeader>
            <PageSectionHeaderContent>
              <PageSectionTitle id="new-search-heading">发起搜索</PageSectionTitle>
              <PageSectionDescription>
                搜索结果展示实际采用的硬条件、研究主题查询与未参与检索的未支持条件。
              </PageSectionDescription>
            </PageSectionHeaderContent>
          </PageSectionHeader>
          <DataRegion>
            <DataRegionContent>
              <SearchUtteranceForm />
            </DataRegionContent>
          </DataRegion>
        </PageSection>
      ) : null}

      <PageSection aria-labelledby="history-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="history-heading">历史运行</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionHeader>本租户的搜索运行记录</DataRegionHeader>
          <DataRegionContent>
            {runs.length === 0 ? (
              <p className="py-6 text-sm text-muted-foreground">还没有搜索运行记录。</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>搜索原句</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead numeric>数据版本</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="max-w-96 truncate">
                        <Link
                          className="font-medium underline underline-offset-4"
                          href={`/search/${run.id}`}
                        >
                          {run.utterance}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <StatusBadge {...statusMeta[run.status]} />
                          {run.failure_reason ? (
                            <span className="text-xs text-muted-foreground">
                              {failureReasonLabels[run.failure_reason]}
                            </span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>{formatDateTime(run.created_at)}</TableCell>
                      <TableCell numeric>
                        {run.data_version ? (
                          <Badge variant="outline">{run.data_version}</Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </DataRegionContent>
          {next_cursor ? (
            <DataRegionFooter>
              <Link
                className="text-sm underline underline-offset-4"
                href={{ query: { cursor: next_cursor } }}
              >
                下一页
              </Link>
            </DataRegionFooter>
          ) : null}
        </DataRegion>
      </PageSection>
    </Page>
  )
}
