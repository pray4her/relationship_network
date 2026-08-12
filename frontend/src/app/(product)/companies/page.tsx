import { Building2Icon } from "lucide-react"
import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { createCompanyAction } from "@/app/actions/companies"
import { CompanyCreateForm } from "@/components/companies/company-create-form"
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
import type { CompanyStatus } from "@/lib/companies-contract"

export const metadata: Metadata = {
  title: "企业管理",
}

const statusLabels: Record<CompanyStatus, string> = {
  active: "活跃",
  archived: "已归档",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

const linkClassName = "font-medium underline underline-offset-4"

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>企业管理</PageTitle>
          <PageDescription>维护租户的企业档案、文档与职位归属。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

export default async function CompaniesPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className={linkClassName} href="/login">
          登录
        </Link>
        后查看企业。
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
    return <NoticePage>你没有加入任何租户，无法管理企业。</NoticePage>
  }

  const canRead = permissions.includes("companies:read")
  const canManage = permissions.includes("companies:manage")

  if (!canRead) {
    return <NoticePage>你没有查看企业的权限。</NoticePage>
  }

  const companiesResult = await loadCompanies(createCompaniesTransport(), session)
  if (companiesResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (companiesResult.kind !== "ok") {
    return <NoticePage>企业数据暂时不可用，请稍后再试。</NoticePage>
  }

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>企业管理</PageTitle>
          <PageDescription>维护租户的企业档案、文档与职位归属。</PageDescription>
        </PageHeaderContent>
      </PageHeader>

      <PageSection aria-labelledby="companies-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="companies-heading">企业列表</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {companiesResult.companies.length === 0 ? (
              <Empty>
                <EmptyMedia>
                  <Building2Icon />
                </EmptyMedia>
                <EmptyHeader>
                  <EmptyTitle>尚未创建企业</EmptyTitle>
                  <EmptyDescription>创建企业后，可以维护企业文档与关联职位。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
                      名称
                    </TableHead>
                    <TableHead className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
                      状态
                    </TableHead>
                    <TableHead className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
                      创建时间
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {companiesResult.companies.map((company) => (
                    <TableRow key={company.id}>
                      <TableCell>
                        <Link className={linkClassName} href={`/companies/${company.id}`}>
                          {company.name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {company.status === "active" ? (
                          <Badge className="bg-success/10 text-success">
                            {statusLabels[company.status]}
                          </Badge>
                        ) : (
                          <Badge variant="secondary">{statusLabels[company.status]}</Badge>
                        )}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatDateTime(company.created_at)}
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
        <FormSection aria-labelledby="create-company-heading">
          <FormSectionHeader>
            <FormSectionTitle id="create-company-heading">创建企业</FormSectionTitle>
            <FormSectionDescription>添加一份新的企业档案。</FormSectionDescription>
          </FormSectionHeader>
          <FormSectionContent>
            <CompanyCreateForm action={createCompanyAction} />
          </FormSectionContent>
        </FormSection>
      ) : null}
    </Page>
  )
}
