import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { AccountPanel } from "@/components/account-panel"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createBillingTransport, loadBillingSummary } from "@/lib/billing-client"
import type { BillingMetric, BillingStatus } from "@/lib/billing-contract"

export const metadata: Metadata = {
  title: "用量与套餐 · Relationship Network",
}

const billingStatusLabels: Record<BillingStatus, string> = {
  active: "已订阅",
  cancelled: "已取消",
  expired: "已过期",
  trialing: "试用中",
}

const billingMetricLabels: Record<BillingMetric, string> = {
  active_jobs: "活跃职位",
  companies: "企业",
  matches: "匹配次数",
  owners: "所有者",
  reports: "报告份数",
  searches: "搜索次数",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

export default async function UsagePage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">用量与套餐</h1>
          <p className="notice">
            请先<Link href="/login">登录</Link>后查看用量与套餐。
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
          <h1 className="panel-title">用量与套餐</h1>
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

  if (auth.view.tenant === null) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">用量与套餐</h1>
          <p className="notice">你没有加入任何租户，无法查看用量与套餐。</p>
        </section>
      </main>
    )
  }

  if (!auth.view.permissions.includes("billing:read")) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">用量与套餐</h1>
          <p className="notice">你没有查看用量与套餐的权限。</p>
        </section>
      </main>
    )
  }

  const result = await loadBillingSummary(createBillingTransport(), session)

  if (result.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  if (result.kind === "notFound") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">用量与套餐</h1>
          <p className="notice">当前租户暂无订阅</p>
        </section>
      </main>
    )
  }

  if (result.kind !== "ok") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">用量与套餐</h1>
          <p className="notice">用量数据暂时不可用，请稍后再试。</p>
        </section>
      </main>
    )
  }

  const { summary } = result

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="plan-heading">
        <h1 className="panel-title" id="plan-heading">
          用量与套餐
        </h1>
        <p>
          当前套餐：{summary.plan.name} v{summary.plan.version}{" "}
          <span className="tag">{billingStatusLabels[summary.status]}</span>
        </p>
        {summary.status === "trialing" && summary.trial_ends_at !== null ? (
          <p>试用到期时间：{formatDateTime(summary.trial_ends_at)}</p>
        ) : null}
        <p>
          当前计费周期：{formatDateTime(summary.current_period_start)} –{" "}
          {formatDateTime(summary.current_period_end)}
        </p>
      </section>

      <section className="panel" aria-labelledby="metrics-heading">
        <h2 className="panel-title" id="metrics-heading">
          配额用量
        </h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>指标</th>
              <th>限额</th>
              <th>已用</th>
              <th>预占中</th>
              <th>剩余</th>
            </tr>
          </thead>
          <tbody>
            {summary.metrics.map((metric) => (
              <tr key={metric.metric}>
                <td>{billingMetricLabels[metric.metric]}</td>
                <td>{metric.limit}</td>
                <td>{metric.used}</td>
                <td>{metric.reserved}</td>
                <td>{metric.remaining}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  )
}
