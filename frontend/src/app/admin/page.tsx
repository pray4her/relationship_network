import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"
import { AccountPanel } from "@/components/account-panel"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { Button } from "@/components/ui/button"
import { createAdminTransport, loadAdminAuditEvents, searchAdminTenants } from "@/lib/admin-client"
import { tenantStatusSchema } from "@/lib/admin-contract"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime, tenantStatusLabels } from "@/lib/admin-view"

export const metadata: Metadata = {
  title: "平台管理 · Relationship Network",
}

type AdminPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

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
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="tenants-heading">
        <h1 className="panel-title" id="tenants-heading">
          租户管理
        </h1>
        <form action="/admin" className="auth-form" method="get">
          <div className="form-field">
            <label className="field-label" htmlFor="tenant-query">
              搜索（名称或标识）
            </label>
            <input
              className="field-input"
              defaultValue={query}
              id="tenant-query"
              name="query"
              placeholder="输入租户名称或 slug"
              type="search"
            />
          </div>
          <div className="form-field">
            <label className="field-label" htmlFor="tenant-status">
              状态
            </label>
            <select
              className="field-input"
              defaultValue={status ?? ""}
              id="tenant-status"
              name="status"
            >
              <option value="">全部</option>
              <option value="active">正常</option>
              <option value="suspended">已暂停</option>
            </select>
          </div>
          <div>
            <Button mode="secondary" type="submit">
              搜索
            </Button>
          </div>
        </form>
        <p className="field-hint">共 {tenantsResult.total} 个租户</p>
        {tenantsResult.tenants.length === 0 ? (
          <p className="field-hint">没有符合条件的租户。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>标识</th>
                <th>状态</th>
                <th>成员数</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {tenantsResult.tenants.map((tenant) => (
                <tr key={tenant.id}>
                  <td>
                    <Link href={`/admin/tenants/${tenant.id}`}>{tenant.name}</Link>
                  </td>
                  <td>{tenant.slug}</td>
                  <td>
                    <span className={tenant.status === "active" ? "tag" : "tag tag-muted"}>
                      {tenantStatusLabels[tenant.status]}
                    </span>
                  </td>
                  <td>{tenant.member_count}</td>
                  <td>{formatDateTime(tenant.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel" aria-labelledby="audit-heading">
        <h2 className="panel-title" id="audit-heading">
          审计日志
        </h2>
        {auditResult.kind !== "ok" ? (
          <p className="notice">审计日志暂时不可用，请稍后再试。</p>
        ) : auditResult.events.length === 0 ? (
          <p className="field-hint">暂无审计事件。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>操作</th>
                <th>目标</th>
                <th>结果</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {auditResult.events.map((event) => (
                <tr key={event.id}>
                  <td>{event.action}</td>
                  <td>{event.target_id}</td>
                  <td>
                    <span className="tag">{event.result}</span>
                  </td>
                  <td>{formatDateTime(event.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  )
}
