import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { tenantStatusAction } from "@/app/actions/admin"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { TenantStatusAction } from "@/components/admin/tenant-status-action"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableRow } from "@/components/ui/table"
import { createAdminTransport, loadAdminTenant } from "@/lib/admin-client"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime, tenantStatusLabels } from "@/lib/admin-view"
import { cn } from "@/lib/utils"

export const metadata: Metadata = {
  title: "租户详情",
}

type AdminTenantPageProps = {
  readonly params: Promise<{ id: string }>
}

const rowHeadClassName = "w-32 font-mono text-xs tracking-wider text-muted-foreground uppercase"

export default async function AdminTenantPage({ params }: AdminTenantPageProps) {
  const { id } = await params

  const guard = await requireAdminView()
  if (guard.kind !== "ok") {
    return <AdminGateNotice failure={guard.kind} title="租户详情" />
  }

  const result = await loadAdminTenant(createAdminTransport(), guard.session, id)

  if (result.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  if (result.kind !== "ok") {
    return (
      <AdminGateNotice
        failure={result.kind === "notFound" ? "unreachable" : result.kind}
        message={
          result.kind === "notFound"
            ? "租户不存在或已被删除。"
            : result.kind === "unreachable"
              ? "租户数据暂时不可用，请稍后再试。"
              : undefined
        }
        title="租户详情"
      >
        <p className="text-sm text-muted-foreground">
          <Link className="font-medium underline underline-offset-4" href="/admin">
            返回租户列表
          </Link>
        </p>
      </AdminGateNotice>
    )
  }

  const tenant = result.tenant

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <section aria-labelledby="tenant-heading">
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold tracking-tight" id="tenant-heading">
              {tenant.name}
            </h1>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Table>
              <TableBody>
                <TableRow>
                  <TableHead className={rowHeadClassName} scope="row">
                    标识
                  </TableHead>
                  <TableCell>{tenant.slug}</TableCell>
                </TableRow>
                <TableRow>
                  <TableHead className={rowHeadClassName} scope="row">
                    状态
                  </TableHead>
                  <TableCell>
                    <Badge
                      className={cn(tenant.status === "active" && "bg-success/10 text-success")}
                      variant="secondary"
                    >
                      {tenantStatusLabels[tenant.status]}
                    </Badge>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableHead className={rowHeadClassName} scope="row">
                    强制 MFA
                  </TableHead>
                  <TableCell>{tenant.mfa_required ? "已开启" : "未开启"}</TableCell>
                </TableRow>
                <TableRow>
                  <TableHead className={rowHeadClassName} scope="row">
                    成员数
                  </TableHead>
                  <TableCell className="tabular-nums">{tenant.member_count}</TableCell>
                </TableRow>
                <TableRow>
                  <TableHead className={rowHeadClassName} scope="row">
                    创建时间
                  </TableHead>
                  <TableCell className="tabular-nums">
                    {formatDateTime(tenant.created_at)}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <TenantStatusAction
              action={tenantStatusAction}
              status={tenant.status}
              tenantId={tenant.id}
            />
            <p className="text-sm text-muted-foreground">
              <Link className="font-medium underline underline-offset-4" href="/admin">
                返回租户列表
              </Link>
            </p>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
