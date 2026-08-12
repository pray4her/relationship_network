import { BriefcaseBusinessIcon } from "lucide-react"
import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"
import { Suspense } from "react"

import { createJobAction } from "@/app/actions/jobs"
import { JobCreateForm } from "@/components/jobs/job-create-form"
import { JobsFilter } from "@/components/jobs/jobs-filter"
import {
  DataRegion,
  DataRegionContent,
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
  PageToolbar,
} from "@/components/layout/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
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

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>职位管理</PageTitle>
          <PageDescription>维护职位档案、状态与相关材料。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
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
      <NoticePage>
        请先
        <Link className={linkClassName} href="/login">
          登录
        </Link>
        后查看职位。
      </NoticePage>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <NoticePage>
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
      </NoticePage>
    )
  }

  const permissions = auth.view.permissions

  if (auth.view.tenant === null) {
    return <NoticePage>你没有加入任何租户，无法管理职位。</NoticePage>
  }

  const canRead = permissions.includes("jobs:read")
  const canManage = permissions.includes("jobs:manage")
  const canReadCompanies = permissions.includes("companies:read")

  if (!canRead) {
    return <NoticePage>你没有查看职位的权限。</NoticePage>
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
    return <NoticePage>职位数据暂时不可用，请稍后再试。</NoticePage>
  }

  const companiesResult = canReadCompanies
    ? await loadCompanies(createCompaniesTransport(), session)
    : null
  const companies = companiesResult?.kind === "ok" ? companiesResult.companies : []
  const companyNameById = new Map(companies.map((company) => [company.id, company.name]))

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>职位管理</PageTitle>
          <PageDescription>维护职位档案、状态与相关材料。</PageDescription>
        </PageHeaderContent>
      </PageHeader>

      <PageSection aria-labelledby="jobs-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="jobs-heading">职位列表</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <PageToolbar aria-label="筛选职位">
          <Suspense>
            <JobsFilter
              companies={companies.map((company) => ({ id: company.id, name: company.name }))}
            />
          </Suspense>
        </PageToolbar>
        <DataRegion>
          <DataRegionContent>
            {jobsResult.jobs.length === 0 ? (
              <Empty>
                <EmptyMedia>
                  <BriefcaseBusinessIcon />
                </EmptyMedia>
                <EmptyHeader>
                  <EmptyTitle>尚未创建职位</EmptyTitle>
                  <EmptyDescription>创建职位草稿后，可以上传材料并启用职位。</EmptyDescription>
                </EmptyHeader>
              </Empty>
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
                      <TableCell className="tabular-nums">
                        {formatDateTime(job.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </DataRegionContent>
        </DataRegion>
      </PageSection>

      {canManage ? (
        <FormSection aria-labelledby="create-job-heading">
          <FormSectionHeader>
            <FormSectionTitle id="create-job-heading">创建职位</FormSectionTitle>
            <FormSectionDescription>为现有企业添加职位草稿。</FormSectionDescription>
          </FormSectionHeader>
          <FormSectionContent>
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
          </FormSectionContent>
        </FormSection>
      ) : null}
    </Page>
  )
}
