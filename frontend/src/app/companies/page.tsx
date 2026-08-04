import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { createCompanyAction } from "@/app/actions/companies"
import { AccountPanel } from "@/components/account-panel"
import { CompanyCreateForm } from "@/components/companies/company-create-form"
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

export default async function CompaniesPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业管理</h1>
          <p className="notice">
            请先<Link href="/login">登录</Link>后查看企业。
          </p>
        </section>
      </main>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业管理</h1>
          <p className="notice">
            {auth.kind === "anonymous" ? (
              <>
                登录已过期，请<Link href="/login">重新登录</Link>。
              </>
            ) : (
              "服务暂时不可用，请稍后再试。"
            )}
          </p>
        </section>
      </main>
    )
  }

  const permissions = auth.view.permissions

  if (auth.view.tenant === null) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业管理</h1>
          <p className="notice">你没有加入任何租户，无法管理企业。</p>
        </section>
      </main>
    )
  }

  const canRead = permissions.includes("companies:read")
  const canManage = permissions.includes("companies:manage")

  if (!canRead) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业管理</h1>
          <p className="notice">你没有查看企业的权限。</p>
        </section>
      </main>
    )
  }

  const companiesResult = await loadCompanies(createCompaniesTransport(), session)
  if (companiesResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (companiesResult.kind !== "ok") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业管理</h1>
          <p className="notice">企业数据暂时不可用，请稍后再试。</p>
        </section>
      </main>
    )
  }

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="companies-heading">
        <h1 className="panel-title" id="companies-heading">
          企业列表
        </h1>
        {companiesResult.companies.length === 0 ? (
          <p className="notice">尚未创建企业。创建后可用于维护职位与匹配。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>状态</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {companiesResult.companies.map((company) => (
                <tr key={company.id}>
                  <td>
                    <Link href={`/companies/${company.id}`}>{company.name}</Link>
                  </td>
                  <td>
                    <span className={company.status === "active" ? "tag" : "tag tag-muted"}>
                      {statusLabels[company.status]}
                    </span>
                  </td>
                  <td>{formatDateTime(company.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {canManage ? (
        <section className="panel" aria-labelledby="create-company-heading">
          <h2 className="panel-title" id="create-company-heading">
            创建企业
          </h2>
          <CompanyCreateForm action={createCompanyAction} />
        </section>
      ) : null}
    </main>
  )
}
