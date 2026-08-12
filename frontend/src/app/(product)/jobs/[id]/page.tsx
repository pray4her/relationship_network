import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { Suspense } from "react"

import {
  activateJobAction,
  archiveJobAction,
  closeJobAction,
  updateJobAction,
  uploadJobMaterialAction,
} from "@/app/actions/jobs"
import { JobActivateButton } from "@/components/jobs/job-activate-button"
import {
  buildJobActivationChecklistItems,
  JobActivationChecklist,
} from "@/components/jobs/job-activation-checklist"
import { JobArchiveButton } from "@/components/jobs/job-archive-button"
import { JobCloseButton } from "@/components/jobs/job-close-button"
import { JobDetailTabs } from "@/components/jobs/job-detail-tabs"
import { JobEditForm } from "@/components/jobs/job-edit-form"
import { JobEventsTable } from "@/components/jobs/job-events-table"
import { JobMaterialUpload } from "@/components/jobs/job-material-upload"
import { JobRequirementGenerator } from "@/components/jobs/requirement-generator"
import {
  RequirementMatchingGateAlert,
  RequirementVersionHistory,
} from "@/components/jobs/requirement-version-history"
import {
  DataRegion,
  DataRegionContent,
  DataRegionFooter,
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
  Page,
  PageActions,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiPublicBaseUrl } from "@/lib/api-url"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createCompaniesTransport, loadCompanies } from "@/lib/companies-client"
import { resolveJobDetailTab } from "@/lib/job-detail-tabs"
import { createRequirementTransport, loadRequirementWorkspace } from "@/lib/job-requirement-client"
import { createJobsTransport, loadJobDetail } from "@/lib/jobs-client"
import type { JobStatus } from "@/lib/jobs-contract"

type JobDetailPageProps = {
  readonly params: Promise<{ readonly id: string }>
  readonly searchParams: Promise<{ readonly [key: string]: string | string[] | undefined }>
}

export const metadata: Metadata = {
  title: "职位详情",
}

const statusLabels: Record<JobStatus, string> = {
  draft: "草稿",
  active: "活跃",
  closed: "已关闭",
  archived: "已归档",
}

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"
const linkClassName = "font-medium underline underline-offset-4"

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
          <PageTitle>职位详情</PageTitle>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

export default async function JobDetailPage({ params, searchParams }: JobDetailPageProps) {
  const { id } = await params
  const query = await searchParams
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className={linkClassName} href="/login">
          登录
        </Link>
        。
      </NoticePage>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return <NoticePage>登录状态无效，请重新登录。</NoticePage>
  }

  if (!auth.view.permissions.includes("jobs:read")) {
    return <NoticePage>你没有查看职位的权限。</NoticePage>
  }

  const permissions = auth.view.permissions
  const [detail, requirement, companiesResult] = await Promise.all([
    loadJobDetail(createJobsTransport(), session, id),
    loadRequirementWorkspace(createRequirementTransport(), session, id),
    permissions.includes("companies:read")
      ? loadCompanies(createCompaniesTransport(), session)
      : Promise.resolve(null),
  ])
  if (detail.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (detail.kind === "notFound") {
    notFound()
  }
  if (detail.kind !== "ok") {
    return <NoticePage>职位详情暂时不可用，请稍后再试。</NoticePage>
  }

  if (requirement.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  const { job, materials, events } = detail
  const canManage = permissions.includes("jobs:manage")
  const isDraft = job.status === "draft"
  const isActive = job.status === "active"
  const isClosed = job.status === "closed"
  const hasEditableDraft =
    requirement.kind === "ok" && requirement.workspace.draft?.status === "editable"
  const matchingBlocked = requirement.kind === "ok" ? requirement.workspace.matching_blocked : false
  const hasConfirmedVersion =
    requirement.kind === "ok" &&
    (requirement.workspace.current_version !== null ||
      requirement.workspace.versions.some((version) => version.is_current))
  const unsupportedCount =
    requirement.kind === "ok"
      ? (requirement.workspace.draft?.result.unsupported_conditions.length ?? 0)
      : 0
  const versionsCount = requirement.kind === "ok" ? requirement.workspace.versions.length : 0
  const activeTab = resolveJobDetailTab(query["tab"], {
    hasEditableDraft,
    matchingBlocked,
  })

  const companyName =
    companiesResult?.kind === "ok"
      ? (companiesResult.companies.find((company) => company.id === job.company_id)?.name ?? null)
      : null

  const showChecklist =
    canManage && (isDraft || matchingBlocked || isActive) && requirement.kind === "ok"
  const checklistItems = showChecklist
    ? buildJobActivationChecklistItems({
        hasConfirmedVersion,
        matchingBlocked,
        materialCount: materials.length,
      })
    : []

  return (
    <Page>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/jobs" />}>职位管理</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{job.title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle className="text-pretty" id="job-detail-heading">
            {job.title}
          </PageTitle>
          <PageDescription>
            {companyName ? <span>所属企业：{companyName}。</span> : null}
            {job.description ? (
              <span className="line-clamp-2">{job.description}</span>
            ) : (
              <span>暂无职位描述。</span>
            )}
          </PageDescription>
        </PageHeaderContent>
        <PageActions>
          <StatusBadge status={job.status} />
          {canManage ? (
            <>
              {isDraft ? (
                <>
                  <JobActivateButton action={activateJobAction} jobId={job.id} />
                  <JobArchiveButton action={archiveJobAction} jobId={job.id} />
                </>
              ) : null}
              {isActive ? <JobCloseButton action={closeJobAction} jobId={job.id} /> : null}
              {isClosed ? (
                <>
                  <JobActivateButton action={activateJobAction} jobId={job.id} />
                  <JobArchiveButton action={archiveJobAction} jobId={job.id} />
                </>
              ) : null}
            </>
          ) : null}
        </PageActions>
      </PageHeader>

      {showChecklist ? <JobActivationChecklist items={checklistItems} jobId={job.id} /> : null}

      <Suspense fallback={null}>
        <JobDetailTabs
          activeTab={activeTab}
          counts={{
            events: events.length,
            materials: materials.length,
            unsupported: unsupportedCount,
            versions: versionsCount,
          }}
          events={
            <PageSection aria-labelledby="events-heading">
              <PageSectionHeader>
                <PageSectionHeaderContent>
                  <PageSectionTitle id="events-heading">操作记录</PageSectionTitle>
                </PageSectionHeaderContent>
              </PageSectionHeader>
              <DataRegion>
                <DataRegionContent>
                  <JobEventsTable events={events} />
                </DataRegionContent>
              </DataRegion>
            </PageSection>
          }
          materials={
            <PageSection aria-labelledby="materials-heading">
              <PageSectionHeader>
                <PageSectionHeaderContent>
                  <PageSectionTitle id="materials-heading">职位材料</PageSectionTitle>
                </PageSectionHeaderContent>
              </PageSectionHeader>
              <DataRegion>
                <DataRegionContent>
                  {materials.length === 0 ? (
                    <Empty>
                      <EmptyHeader>
                        <EmptyTitle>尚未上传材料</EmptyTitle>
                        <EmptyDescription>
                          上传职位材料后，可在此查看抽取文本和下载原文件。
                        </EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className={headClassName}>文件名</TableHead>
                          <TableHead className={headClassName}>大小</TableHead>
                          <TableHead className={headClassName}>抽取文本预览</TableHead>
                          <TableHead className={headClassName}>上传时间</TableHead>
                          <TableHead className={headClassName}>下载</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {materials.map((material) => (
                          <TableRow key={material.id}>
                            <TableCell>{material.original_filename}</TableCell>
                            <TableCell className="tabular-nums">{material.byte_size} B</TableCell>
                            <TableCell className="max-w-md truncate">
                              {material.extracted_text.slice(0, 120) || "暂无提取文本"}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {new Date(material.created_at).toLocaleString("zh-CN", {
                                hour12: false,
                              })}
                            </TableCell>
                            <TableCell>
                              <a
                                className={linkClassName}
                                href={`${apiPublicBaseUrl()}/jobs/${job.id}/materials/${material.id}/content`}
                              >
                                下载
                              </a>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </DataRegionContent>
                {canManage && isDraft ? (
                  <DataRegionFooter>
                    <JobMaterialUpload action={uploadJobMaterialAction} jobId={job.id} />
                  </DataRegionFooter>
                ) : null}
              </DataRegion>
            </PageSection>
          }
          overview={
            <div className="flex min-w-0 flex-col gap-8">
              {canManage && isDraft ? (
                <FormSection aria-labelledby="edit-job-heading">
                  <FormSectionHeader>
                    <FormSectionTitle id="edit-job-heading">编辑职位</FormSectionTitle>
                    <FormSectionDescription>更新草稿的职位名称和说明。</FormSectionDescription>
                  </FormSectionHeader>
                  <FormSectionContent>
                    <JobEditForm
                      action={updateJobAction}
                      description={job.description}
                      jobId={job.id}
                      title={job.title}
                    />
                  </FormSectionContent>
                </FormSection>
              ) : (
                <PageSection aria-labelledby="job-summary-heading">
                  <PageSectionHeader>
                    <PageSectionHeaderContent>
                      <PageSectionTitle id="job-summary-heading">职位摘要</PageSectionTitle>
                    </PageSectionHeaderContent>
                  </PageSectionHeader>
                  <DataRegion>
                    <DataRegionContent className="flex flex-col gap-3 px-5 py-4">
                      <p className="m-0 text-sm text-muted-foreground">
                        状态：{statusLabels[job.status]}
                        {companyName ? ` · 企业：${companyName}` : null}
                      </p>
                      <p className="m-0 whitespace-pre-wrap break-words text-sm leading-normal">
                        {job.description || "暂无职位描述。"}
                      </p>
                      <p className="m-0 text-sm text-muted-foreground tabular-nums">
                        材料 {materials.length.toLocaleString("zh-CN")} 份
                        {requirement.kind === "ok"
                          ? ` · 需求版本 ${versionsCount.toLocaleString("zh-CN")} 个`
                          : null}
                        {hasConfirmedVersion ? " · 已有确认版本" : " · 尚无确认版本"}
                      </p>
                    </DataRegionContent>
                  </DataRegion>
                </PageSection>
              )}
            </div>
          }
          requirement={
            <PageSection aria-labelledby="requirement-generation-heading">
              <PageSectionHeader>
                <PageSectionHeaderContent>
                  <PageSectionTitle id="requirement-generation-heading">
                    职位需求草稿
                  </PageSectionTitle>
                </PageSectionHeaderContent>
              </PageSectionHeader>
              {requirement.kind === "ok" ? (
                <>
                  <RequirementMatchingGateAlert workspace={requirement.workspace} />
                  <JobRequirementGenerator
                    archived={job.status === "archived"}
                    canManage={canManage}
                    jobId={job.id}
                    workspace={requirement.workspace}
                  />
                </>
              ) : (
                <Alert>
                  <AlertDescription>
                    职位需求工作区暂时不可用。职位详情和已有材料仍可继续查看。
                  </AlertDescription>
                </Alert>
              )}
            </PageSection>
          }
          versions={
            <PageSection aria-labelledby="requirement-versions-heading">
              <PageSectionHeader>
                <PageSectionHeaderContent>
                  <PageSectionTitle id="requirement-versions-heading">
                    职位需求版本
                  </PageSectionTitle>
                </PageSectionHeaderContent>
              </PageSectionHeader>
              {requirement.kind === "ok" ? (
                <RequirementVersionHistory
                  archived={job.status === "archived"}
                  canManage={canManage}
                  hasEditableDraft={hasEditableDraft}
                  jobId={job.id}
                  versions={requirement.workspace.versions}
                />
              ) : (
                <Alert>
                  <AlertDescription>职位需求版本历史暂时不可用。</AlertDescription>
                </Alert>
              )}
            </PageSection>
          }
        />
      </Suspense>
    </Page>
  )
}
