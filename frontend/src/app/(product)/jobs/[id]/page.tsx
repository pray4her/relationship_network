import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import {
  activateJobAction,
  archiveJobAction,
  closeJobAction,
  updateJobAction,
  uploadJobMaterialAction,
} from "@/app/actions/jobs"
import { JobActivateButton } from "@/components/jobs/job-activate-button"
import { JobArchiveButton } from "@/components/jobs/job-archive-button"
import { JobCloseButton } from "@/components/jobs/job-close-button"
import { JobEditForm } from "@/components/jobs/job-edit-form"
import { JobMaterialUpload } from "@/components/jobs/job-material-upload"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardContent, CardHeader } from "@/components/ui/card"
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
import { createJobsTransport, loadJobDetail } from "@/lib/jobs-client"
import type { JobStatus } from "@/lib/jobs-contract"

type JobDetailPageProps = {
  readonly params: Promise<{ readonly id: string }>
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

const eventLabels: Record<string, string> = {
  "job.create": "创建",
  "job.update": "编辑",
  "job.activate": "启用",
  "job.close": "关闭",
  "job.archive": "归档",
  "job.material_upload": "上传材料",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
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

function NoticeCard({ children }: { readonly children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight">职位详情</h1>
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

export default async function JobDetailPage({ params }: JobDetailPageProps) {
  const { id } = await params
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticeCard>
        请先
        <Link className={linkClassName} href="/login">
          登录
        </Link>
        。
      </NoticeCard>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return <NoticeCard>登录状态无效，请重新登录。</NoticeCard>
  }

  if (!auth.view.permissions.includes("jobs:read")) {
    return <NoticeCard>你没有查看职位的权限。</NoticeCard>
  }

  const detail = await loadJobDetail(createJobsTransport(), session, id)
  if (detail.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (detail.kind === "notFound") {
    notFound()
  }
  if (detail.kind !== "ok") {
    return <NoticeCard>职位详情暂时不可用，请稍后再试。</NoticeCard>
  }

  const { job, materials, events } = detail
  const permissions = auth.view.permissions
  const canManage = permissions.includes("jobs:manage")
  const isDraft = job.status === "draft"
  const isActive = job.status === "active"
  const isClosed = job.status === "closed"

  let companyName: string | null = null
  if (permissions.includes("companies:read")) {
    const companiesResult = await loadCompanies(createCompaniesTransport(), session)
    if (companiesResult.kind === "ok") {
      companyName =
        companiesResult.companies.find((company) => company.id === job.company_id)?.name ?? null
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <Card aria-labelledby="job-detail-heading">
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight" id="job-detail-heading">
            {job.title}
          </h1>
          <CardAction>
            <StatusBadge status={job.status} />
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p>
            <Link
              className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
              href="/jobs"
            >
              ← 返回职位列表
            </Link>
          </p>
          {companyName ? (
            <p className="text-sm text-muted-foreground">所属企业：{companyName}</p>
          ) : null}
          <p className="text-sm text-muted-foreground">{job.description || "暂无职位描述。"}</p>
          {canManage ? (
            <div className="flex flex-wrap items-start gap-3">
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
            </div>
          ) : null}
        </CardContent>
      </Card>

      {canManage && isDraft ? (
        <Card aria-labelledby="edit-job-heading">
          <CardHeader>
            <h2 className="text-lg font-semibold" id="edit-job-heading">
              编辑职位
            </h2>
          </CardHeader>
          <CardContent>
            <JobEditForm
              action={updateJobAction}
              jobId={job.id}
              title={job.title}
              description={job.description}
            />
          </CardContent>
        </Card>
      ) : null}

      <Card aria-labelledby="materials-heading">
        <CardHeader>
          <h2 className="text-lg font-semibold" id="materials-heading">
            职位材料
          </h2>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {materials.length === 0 ? (
            <p className="text-sm text-muted-foreground">尚未上传材料。</p>
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
                      {material.extracted_text.slice(0, 120) || "—"}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {formatDateTime(material.created_at)}
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
          {canManage && isDraft ? (
            <JobMaterialUpload action={uploadJobMaterialAction} jobId={job.id} />
          ) : null}
        </CardContent>
      </Card>

      <Card aria-labelledby="events-heading">
        <CardHeader>
          <h2 className="text-lg font-semibold" id="events-heading">
            操作记录
          </h2>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无操作记录。</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className={headClassName}>时间</TableHead>
                  <TableHead className={headClassName}>动作</TableHead>
                  <TableHead className={headClassName}>结果</TableHead>
                  <TableHead className={headClassName}>详情</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="tabular-nums">
                      {formatDateTime(event.created_at)}
                    </TableCell>
                    <TableCell>{eventLabels[event.action] ?? event.action}</TableCell>
                    <TableCell>{event.result}</TableCell>
                    <TableCell>{event.detail || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
