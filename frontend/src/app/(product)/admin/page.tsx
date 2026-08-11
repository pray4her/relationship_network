import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { Page, PageTitle } from "@/components/layout/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { createAdminTransport, loadAdminAuditEvents, searchAdminTenants } from "@/lib/admin-client"
import { tenantStatusSchema } from "@/lib/admin-contract"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime, tenantStatusLabels } from "@/lib/admin-view"
import { cn } from "@/lib/utils"

export const metadata: Metadata = {
  title: "平台管理",
}

type AdminPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

const selectClassName =
  "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

const tableHeadClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function firstParam(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : ""
}

function TenantStatusBadge({ status }: { readonly status: keyof typeof tenantStatusLabels }) {
  return (
    <Badge className={cn(status === "active" && "bg-success/10 text-success")} variant="secondary">
      {tenantStatusLabels[status]}
    </Badge>
  )
}

export default async function AdminPage({ searchParams }: AdminPageProps) {
  const params = await searchParams
  const query = firstParam(params["query"]).trim()
  const rawStatus = firstParam(params["status"])
  const parsedStatus = tenantStatusSchema.safeParse(rawStatus)
  const status = parsedStatus.success ? parsedStatus.data : null

  const guard = await requireAdminView()
  if (guard.kind !== "ok") {
    return <AdminGateNotice failure={guard.kind} title="平台管理" />
  }
  const session = guard.session

  const adminTransport = createAdminTransport()
  const [tenantsResult, auditResult] = await Promise.all([
    searchAdminTenants(adminTransport, session, {
      query: query === "" ? null : query,
      status,
    }),
    loadAdminAuditEvents(adminTransport, session),
  ])

  if (tenantsResult.kind === "mfaRequired" || auditResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  if (tenantsResult.kind === "anonymous" || auditResult.kind === "anonymous") {
    return <AdminGateNotice failure="anonymous" title="平台管理" />
  }

  if (tenantsResult.kind === "forbidden" || auditResult.kind === "forbidden") {
    return <AdminGateNotice failure="forbidden" title="平台管理" />
  }

  if (tenantsResult.kind !== "ok") {
    return (
      <AdminGateNotice
        failure="unreachable"
        message="租户数据暂时不可用，请稍后再试。"
        title="平台管理"
      />
    )
  }

  return (
    <Page>
      <section aria-labelledby="tenants-heading">
        <Card>
          <CardHeader>
            <PageTitle id="tenants-heading">租户管理</PageTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <form action="/admin" className="flex flex-wrap items-end gap-4" method="get">
              <Field className="w-full sm:w-64">
                <FieldLabel htmlFor="tenant-query">搜索（名称或标识）</FieldLabel>
                <Input
                  defaultValue={query}
                  id="tenant-query"
                  name="query"
                  placeholder="输入租户名称或 slug"
                  type="search"
                />
              </Field>
              <Field className="w-full sm:w-48">
                <FieldLabel htmlFor="tenant-status">状态</FieldLabel>
                <select
                  className={selectClassName}
                  defaultValue={status ?? ""}
                  id="tenant-status"
                  name="status"
                >
                  <option value="">全部</option>
                  <option value="active">正常</option>
                  <option value="suspended">已暂停</option>
                </select>
              </Field>
              <Button type="submit" variant="secondary">
                搜索
              </Button>
            </form>
            <p className="text-sm text-muted-foreground">共 {tenantsResult.total} 个租户</p>
            <p className="text-sm text-muted-foreground">
              <Link className="font-medium underline underline-offset-4" href="/admin/orders">
                前往线下订单审核
              </Link>
              <span aria-hidden="true"> · </span>
              <Link
                className="font-medium underline underline-offset-4"
                href="/admin/llm-configuration"
              >
                管理 LLM 配置
              </Link>
            </p>
            {tenantsResult.tenants.length === 0 ? (
              <p className="text-sm text-muted-foreground">没有符合条件的租户。</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={tableHeadClassName}>名称</TableHead>
                    <TableHead className={tableHeadClassName}>标识</TableHead>
                    <TableHead className={tableHeadClassName}>状态</TableHead>
                    <TableHead className={tableHeadClassName}>成员数</TableHead>
                    <TableHead className={tableHeadClassName}>创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tenantsResult.tenants.map((tenant) => (
                    <TableRow key={tenant.id}>
                      <TableCell>
                        <Link
                          className="font-medium underline underline-offset-4"
                          href={`/admin/tenants/${tenant.id}`}
                        >
                          {tenant.name}
                        </Link>
                      </TableCell>
                      <TableCell>{tenant.slug}</TableCell>
                      <TableCell>
                        <TenantStatusBadge status={tenant.status} />
                      </TableCell>
                      <TableCell className="tabular-nums">{tenant.member_count}</TableCell>
                      <TableCell className="tabular-nums">
                        {formatDateTime(tenant.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="audit-heading">
        <Card>
          <CardHeader>
            <h2 className="text-xl font-semibold tracking-tight" id="audit-heading">
              审计日志
            </h2>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {auditResult.kind !== "ok" ? (
              <Alert>
                <AlertDescription>审计日志暂时不可用，请稍后再试。</AlertDescription>
              </Alert>
            ) : auditResult.events.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无审计事件。</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={tableHeadClassName}>操作</TableHead>
                    <TableHead className={tableHeadClassName}>目标</TableHead>
                    <TableHead className={tableHeadClassName}>结果</TableHead>
                    <TableHead className={tableHeadClassName}>时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditResult.events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell>{event.action}</TableCell>
                      <TableCell>{event.target_id}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{event.result}</Badge>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatDateTime(event.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </section>
    </Page>
  )
}
