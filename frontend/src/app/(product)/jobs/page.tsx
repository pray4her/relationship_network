import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"
import { Suspense } from "react"

import { createJobAction } from "@/app/actions/jobs"
import { JobCreateForm } from "@/components/jobs/job-create-form"
import { JobsFilter } from "@/components/jobs/jobs-filter"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createCompaniesTransport, loadCompanies } from "@/lib/companies-client"
import { createJobsTransport, loadJobs } from "@/lib/jobs-client"
import { type JobStatus, jobStatusSchema } from "@/lib/jobs-contract"

export const metadata: Metadata = {
  title: "职位管理",
}

const statusLabels: Record<JobStatus, string> = {
  draft: "草稿",
  active: "活跃",
  closed: "已关闭",
  archived: "已归档",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

const linkClassName = "font-medium underline underline-offset-4"
const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function StatusBadge({ status }: { readonly status: JobStatus }) {
  if (status === "active") {
    return <Badge className="bg-success/10 text-success">{statusLabels[status]}</Badge>
  }
  if (status === "draft") {
    return <Badge variant="outline">{statusLabels[status]}</Badge>
  }
  return <Badge variant="secondary">{statusLabels[status]}</Badge>
}

function NoticeCard({ children }: { readonly children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight">职位管理</h1>
        </CardHeader>
        <CardContent>
          <Alert>
            <AlertDescription>{children}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    </main>
  )
}

type JobsPageProps = {
  readonly searchParams: Promise<{ readonly [key: string]: string | string[] | undefined }>
}

export default async function JobsPage({ searchParams }: JobsPageProps) {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticeCard>
        请先
        <Link className={linkClassName} href="/login">
          登录
        </Link>
        后查看职位。
      </NoticeCard>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <NoticeCard>
        {auth.kind === "anonymous" ? (
          <>
            登录已过期，请
            <Link className={linkClassName} href="/login">
              重新登录
            </Link>
            。
          </>
        ) : (
          "服务暂时不可用，请稍后再试。"
        )}
      </NoticeCard>
    )
  }

  const permissions = auth.view.permissions

  if (auth.view.tenant === null) {
    return <NoticeCard>你没有加入任何租户，无法管理职位。</NoticeCard>
  }

  const canRead = permissions.includes("jobs:read")
  const canManage = permissions.includes("jobs:manage")
  const canReadCompanies = permissions.includes("companies:read")

  if (!canRead) {
    return <NoticeCard>你没有查看职位的权限。</NoticeCard>
  }

  const params = await searchParams
  const statusRaw = params["status"]
  const companyIdRaw = params["company_id"]
  const statusParam = typeof statusRaw === "string" ? statusRaw : ""
  const companyIdParam = typeof companyIdRaw === "string" ? companyIdRaw : ""
  const parsedStatus = jobStatusSchema.safeParse(statusParam)
  const filters: { status?: JobStatus; companyId?: string } = {}
  if (parsedStatus.success) {
    filters.status = parsedStatus.data
  }
  if (companyIdParam) {
    filters.companyId = companyIdParam
  }

  const jobsResult = await loadJobs(createJobsTransport(), session, filters)
  if (jobsResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (jobsResult.kind !== "ok") {
    return <NoticeCard>职位数据暂时不可用，请稍后再试。</NoticeCard>
  }

  const companiesResult = canReadCompanies
    ? await loadCompanies(createCompaniesTransport(), session)
    : null
  const companies = companiesResult?.kind === "ok" ? companiesResult.companies : []
  const companyNameById = new Map(companies.map((company) => [company.id, company.name]))

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <Card aria-labelledby="jobs-heading">
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight" id="jobs-heading">
            职位列表
          </h1>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Suspense>
            <JobsFilter
              companies={companies.map((company) => ({ id: company.id, name: company.name }))}
            />
          </Suspense>
          {jobsResult.jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              尚未创建职位。创建草稿后可上传材料并启用。
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className={headClassName}>职位名称</TableHead>
                  <TableHead className={headClassName}>所属企业</TableHead>
                  <TableHead className={headClassName}>状态</TableHead>
                  <TableHead className={headClassName}>创建时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobsResult.jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>
                      <Link className={linkClassName} href={`/jobs/${job.id}`}>
                        {job.title}
                      </Link>
                    </TableCell>
                    <TableCell>{companyNameById.get(job.company_id) ?? "—"}</TableCell>
                    <TableCell>
                      <StatusBadge status={job.status} />
                    </TableCell>
                    <TableCell className="tabular-nums">{formatDateTime(job.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {canManage ? (
        <Card aria-labelledby="create-job-heading">
          <CardHeader>
            <h2 className="text-lg font-semibold" id="create-job-heading">
              创建职位
            </h2>
          </CardHeader>
          <CardContent>
            {companies.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                创建职位前请先在企业页创建至少一家企业。
              </p>
            ) : (
              <JobCreateForm
                action={createJobAction}
                companies={companies.map((company) => ({ id: company.id, name: company.name }))}
              />
            )}
          </CardContent>
        </Card>
      ) : null}
    </main>
  )
}
