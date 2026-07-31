import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { tenantStatusAction } from "@/app/actions/admin"
import { AccountPanel } from "@/components/account-panel"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { TenantStatusAction } from "@/components/admin/tenant-status-action"
import { createAdminTransport, loadAdminTenant } from "@/lib/admin-client"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime, tenantStatusLabels } from "@/lib/admin-view"

export const metadata: Metadata = {
  title: "租户详情 · Relationship Network",
}

type AdminTenantPageProps = {
  readonly params: Promise<{ id: string }>
}

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
        <p className="field-hint">
          <Link href="/admin">返回租户列表</Link>
        </p>
      </AdminGateNotice>
    )
  }

  const tenant = result.tenant

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="tenant-heading">
        <h1 className="panel-title" id="tenant-heading">
          {tenant.name}
        </h1>
        <table className="data-table">
          <tbody>
            <tr>
              <th>标识</th>
              <td>{tenant.slug}</td>
            </tr>
            <tr>
              <th>状态</th>
              <td>
                <span className={tenant.status === "active" ? "tag" : "tag tag-muted"}>
                  {tenantStatusLabels[tenant.status]}
                </span>
              </td>
            </tr>
            <tr>
              <th>强制 MFA</th>
              <td>{tenant.mfa_required ? "已开启" : "未开启"}</td>
            </tr>
            <tr>
              <th>成员数</th>
              <td>{tenant.member_count}</td>
            </tr>
            <tr>
              <th>创建时间</th>
              <td>{formatDateTime(tenant.created_at)}</td>
            </tr>
          </tbody>
        </table>
        <TenantStatusAction
          action={tenantStatusAction}
          status={tenant.status}
          tenantId={tenant.id}
        />
        <p className="field-hint">
          <Link href="/admin">返回租户列表</Link>
        </p>
      </section>
    </main>
  )
}
