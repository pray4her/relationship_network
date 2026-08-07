import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import {
  archiveCompanyAction,
  updateCompanyAction,
  uploadCompanyDocumentAction,
} from "@/app/actions/companies"
import { AccountPanel } from "@/components/account-panel"
import { CompanyArchiveButton } from "@/components/companies/company-archive-button"
import { CompanyDocumentUpload } from "@/components/companies/company-document-upload"
import { CompanyEditForm } from "@/components/companies/company-edit-form"
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
import { createCompaniesTransport, loadCompanyDetail } from "@/lib/companies-client"

type CompanyDetailPageProps = {
  readonly params: Promise<{ readonly id: string }>
}

export const metadata: Metadata = {
  title: "企业详情 · Relationship Network",
}

const eventLabels: Record<string, string> = {
  "company.create": "创建",
  "company.update": "编辑",
  "company.archive": "归档",
  "company.document_upload": "上传文档",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function NoticeCard({ children }: { readonly children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight">企业详情</h1>
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

export default async function CompanyDetailPage({ params }: CompanyDetailPageProps) {
  const { id } = await params
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticeCard>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
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

  if (!auth.view.permissions.includes("companies:read")) {
    return <NoticeCard>你没有查看企业的权限。</NoticeCard>
  }

  const detail = await loadCompanyDetail(createCompaniesTransport(), session, id)
  if (detail.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (detail.kind === "notFound") {
    notFound()
  }
  if (detail.kind !== "ok") {
    return <NoticeCard>企业详情暂时不可用，请稍后再试。</NoticeCard>
  }

  const { company, documents, events } = detail
  const canManage = auth.view.permissions.includes("companies:manage")
  const isActive = company.status === "active"

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />

      <Card aria-labelledby="company-detail-heading">
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight" id="company-detail-heading">
            {company.name}
          </h1>
          <CardAction>
            {isActive ? (
              <Badge className="bg-success/10 text-success">活跃</Badge>
            ) : (
              <Badge variant="secondary">已归档</Badge>
            )}
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p>
            <Link
              className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
              href="/companies"
            >
              ← 返回企业列表
            </Link>
          </p>
          <p className="text-sm text-muted-foreground">
            {company.profile_text || "暂无企业简介。"}
          </p>
        </CardContent>
      </Card>

      {canManage && isActive ? (
        <Card aria-labelledby="edit-company-heading">
          <CardHeader>
            <h2 className="text-lg font-semibold" id="edit-company-heading">
              编辑企业
            </h2>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <CompanyEditForm
              action={updateCompanyAction}
              companyId={company.id}
              name={company.name}
              profileText={company.profile_text}
            />
            <CompanyArchiveButton action={archiveCompanyAction} companyId={company.id} />
          </CardContent>
        </Card>
      ) : null}

      <Card aria-labelledby="documents-heading">
        <CardHeader>
          <h2 className="text-lg font-semibold" id="documents-heading">
            企业文档
          </h2>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">尚未上传文档。</p>
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
                {documents.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell>{document.original_filename}</TableCell>
                    <TableCell className="tabular-nums">{document.byte_size} B</TableCell>
                    <TableCell className="max-w-md truncate">
                      {document.extracted_text.slice(0, 120) || "—"}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {formatDateTime(document.created_at)}
                    </TableCell>
                    <TableCell>
                      <a
                        className="font-medium underline underline-offset-4"
                        href={`${apiPublicBaseUrl()}/companies/${company.id}/documents/${document.id}/content`}
                      >
                        下载
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {canManage && isActive ? (
            <CompanyDocumentUpload action={uploadCompanyDocumentAction} companyId={company.id} />
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
