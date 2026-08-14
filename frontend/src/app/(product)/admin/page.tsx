import { SearchXIcon } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { adminTableHeadClassName, TenantStatusBadge } from "@/components/admin/admin-status-badges"
import { FilterSelect } from "@/components/admin/filter-select"
import {
  DataRegion,
  DataRegionContent,
  DataRegionHeader,
  Page,
  PageActions,
  PageDescription,
  PageEyebrow,
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
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
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
import { formatDateTime } from "@/lib/format"

export const metadata: Metadata = {
  title: "平台管理",
}

type AdminPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

const linkClassName = "font-medium underline underline-offset-4"

function firstParam(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : ""
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
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理</PageEyebrow>
          <PageTitle>租户管理</PageTitle>
          <PageDescription>检索租户、查看状态，并跳转到订单与 LLM 管理。</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Link className={linkClassName} href="/admin/orders">
            线下订单审核
          </Link>
          <Link className={linkClassName} href="/admin/llm-configuration">
            LLM 配置
          </Link>
          <Link className={linkClassName} href="/admin/llm-calls">
            LLM 调用
          </Link>
        </PageActions>
      </PageHeader>

      <PageSection aria-labelledby="tenant-list-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="tenant-list-heading">租户列表</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <PageToolbar render={<form action="/admin" method="get" />}>
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
            <FilterSelect defaultValue={status ?? ""} id="tenant-status" name="status">
              <option value="">全部</option>
              <option value="active">正常</option>
              <option value="suspended">已暂停</option>
            </FilterSelect>
          </Field>
          <Button type="submit" variant="secondary">
            筛选
          </Button>
          <Button render={<Link href="/admin" />} variant="ghost">
            清除
          </Button>
        </PageToolbar>
        <DataRegion>
          <DataRegionHeader>
            <p className="m-0 font-medium text-foreground">检索结果</p>
            <Badge variant="outline">共 {tenantsResult.total} 个租户</Badge>
          </DataRegionHeader>
          <DataRegionContent>
            {tenantsResult.tenants.length === 0 ? (
              <Empty>
                <EmptyMedia>
                  <SearchXIcon />
                </EmptyMedia>
                <EmptyHeader>
                  <EmptyTitle>没有符合条件的租户</EmptyTitle>
                  <EmptyDescription>调整筛选条件后再试。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={adminTableHeadClassName}>名称</TableHead>
                    <TableHead className={adminTableHeadClassName}>标识</TableHead>
                    <TableHead className={adminTableHeadClassName}>状态</TableHead>
                    <TableHead className={adminTableHeadClassName}>成员数</TableHead>
                    <TableHead className={adminTableHeadClassName}>创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tenantsResult.tenants.map((tenant) => (
                    <TableRow key={tenant.id}>
                      <TableCell>
                        <Link className={linkClassName} href={`/admin/tenants/${tenant.id}`}>
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
          </DataRegionContent>
        </DataRegion>
      </PageSection>

      <PageSection aria-labelledby="audit-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="audit-heading">审计日志</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {auditResult.kind !== "ok" ? (
              <div className="p-5">
                <Alert>
                  <AlertDescription>审计日志暂时不可用，请稍后再试。</AlertDescription>
                </Alert>
              </div>
            ) : auditResult.events.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>暂无审计事件</EmptyTitle>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={adminTableHeadClassName}>操作</TableHead>
                    <TableHead className={adminTableHeadClassName}>目标</TableHead>
                    <TableHead className={adminTableHeadClassName}>结果</TableHead>
                    <TableHead className={adminTableHeadClassName}>时间</TableHead>
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
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
