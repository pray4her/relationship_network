import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { createCompanyAction } from "@/app/actions/companies"
import { AccountPanel } from "@/components/account-panel"
import { CompanyCreateForm } from "@/components/companies/company-create-form"
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
import type { CompanyStatus } from "@/lib/companies-contract"

export const metadata: Metadata = {
  title: "企业管理 · Relationship Network",
}

const statusLabels: Record<CompanyStatus, string> = {
  active: "活跃",
  archived: "已归档",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

const linkClassName = "font-medium underline underline-offset-4"

function NoticeCard({ children }: { readonly children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight">企业管理</h1>
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

export default async function CompaniesPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticeCard>
        请先
        <Link className={linkClassName} href="/login">
          登录
        </Link>
        后查看企业。
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
    return <NoticeCard>你没有加入任何租户，无法管理企业。</NoticeCard>
  }

  const canRead = permissions.includes("companies:read")
  const canManage = permissions.includes("companies:manage")

  if (!canRead) {
    return <NoticeCard>你没有查看企业的权限。</NoticeCard>
  }

  const companiesResult = await loadCompanies(createCompaniesTransport(), session)
  if (companiesResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (companiesResult.kind !== "ok") {
    return <NoticeCard>企业数据暂时不可用，请稍后再试。</NoticeCard>
  }

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />

      <Card aria-labelledby="companies-heading">
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight" id="companies-heading">
            企业列表
          </h1>
        </CardHeader>
        <CardContent>
          {companiesResult.companies.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              尚未创建企业。创建后可用于维护职位与匹配。
            </p>
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
        </CardContent>
      </Card>

      {canManage ? (
        <Card aria-labelledby="create-company-heading">
          <CardHeader>
            <h2 className="text-lg font-semibold" id="create-company-heading">
              创建企业
            </h2>
          </CardHeader>
          <CardContent>
            <CompanyCreateForm action={createCompanyAction} />
          </CardContent>
        </Card>
      ) : null}
    </main>
  )
}
