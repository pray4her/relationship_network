import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import {
  archiveCompanyAction,
  updateCompanyAction,
  uploadCompanyDocumentAction,
} from "@/app/actions/companies"
import { CompanyArchiveButton } from "@/components/companies/company-archive-button"
import { CompanyDocumentUpload } from "@/components/companies/company-document-upload"
import { CompanyEditForm } from "@/components/companies/company-edit-form"
import { companyStatusMeta } from "@/components/companies/company-status"
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
import { StatusBadge } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
import { createCompaniesTransport, loadCompanyDetail } from "@/lib/companies-client"
import { formatBytes, formatDateTime } from "@/lib/format"

type CompanyDetailPageProps = {
  readonly params: Promise<{ readonly id: string }>
}

export const metadata: Metadata = {
  title: "企业详情",
}

const eventLabels: Record<string, string> = {
  "company.create": "创建",
  "company.update": "编辑",
  "company.archive": "归档",
  "company.document_upload": "上传文档",
}

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>企业详情</PageTitle>
          <PageDescription>查看企业档案、文档与操作记录。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

export default async function CompanyDetailPage({ params }: CompanyDetailPageProps) {
  const { id } = await params
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
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

  if (!auth.view.permissions.includes("companies:read")) {
    return <NoticePage>你没有查看企业的权限。</NoticePage>
  }

  const detail = await loadCompanyDetail(createCompaniesTransport(), session, id)
  if (detail.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (detail.kind === "notFound") {
    notFound()
  }
  if (detail.kind !== "ok") {
    return <NoticePage>企业详情暂时不可用，请稍后再试。</NoticePage>
  }

  const { company, documents, events } = detail
  const canManage = auth.view.permissions.includes("companies:manage")
  const isActive = company.status === "active"

  return (
    <Page>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/companies" />}>企业管理</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{company.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle id="company-detail-heading">{company.name}</PageTitle>
          <PageDescription>{company.profile_text || "暂无企业简介。"}</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <StatusBadge {...companyStatusMeta[company.status]} />
        </PageActions>
      </PageHeader>

      {canManage && isActive ? (
        <FormSection aria-labelledby="edit-company-heading">
          <FormSectionHeader>
            <FormSectionTitle id="edit-company-heading">编辑企业</FormSectionTitle>
            <FormSectionDescription>更新企业名称、简介或归档企业。</FormSectionDescription>
          </FormSectionHeader>
          <FormSectionContent>
            <CompanyEditForm
              action={updateCompanyAction}
              companyId={company.id}
              name={company.name}
              profileText={company.profile_text}
            />
            <CompanyArchiveButton action={archiveCompanyAction} companyId={company.id} />
          </FormSectionContent>
        </FormSection>
      ) : null}

      <PageSection aria-labelledby="documents-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="documents-heading">企业文档</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {documents.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>尚未上传文档</EmptyTitle>
                  <EmptyDescription>
                    上传企业资料后，可在此查看抽取文本和下载原文件。
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={headClassName}>文件名</TableHead>
                    <TableHead className={headClassName} numeric>
                      大小
                    </TableHead>
                    <TableHead className={headClassName}>抽取文本预览</TableHead>
                    <TableHead className={`${headClassName} max-md:hidden`}>上传时间</TableHead>
                    <TableHead className={headClassName}>下载</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((document) => (
                    <TableRow key={document.id}>
                      <TableCell>{document.original_filename}</TableCell>
                      <TableCell numeric>{formatBytes(document.byte_size)}</TableCell>
                      <TableCell className="max-w-md truncate">
                        {document.extracted_text.slice(0, 120) || "—"}
                      </TableCell>
                      <TableCell className="tabular-nums max-md:hidden">
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
          </DataRegionContent>
          {canManage && isActive ? (
            <DataRegionFooter>
              <CompanyDocumentUpload action={uploadCompanyDocumentAction} companyId={company.id} />
            </DataRegionFooter>
          ) : null}
        </DataRegion>
      </PageSection>

      <PageSection aria-labelledby="events-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="events-heading">操作记录</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {events.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>暂无操作记录</EmptyTitle>
                </EmptyHeader>
              </Empty>
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
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
