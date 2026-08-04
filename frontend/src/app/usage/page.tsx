import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { cancelSubscriptionAction, submitOrderAction } from "@/app/actions/orders"
import { AccountPanel } from "@/components/account-panel"
import { CancelSubscriptionAction } from "@/components/billing/cancel-subscription-action"
import { OrderRequestForm } from "@/components/billing/order-request-form"
import { ReadOnlyBanner } from "@/components/billing/read-only-banner"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createBillingTransport, loadBillingSummary } from "@/lib/billing-client"
import type { BillingMetric, BillingStatus } from "@/lib/billing-contract"
import { createOrdersTransport, listOrders, type OrderListResult } from "@/lib/orders-client"
import { formatAmountCents, orderStatusLabels } from "@/lib/orders-view"

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

type OrderSectionsProps = {
  readonly canManage: boolean
  readonly ordersResult: OrderListResult
}

function OrderSections({ canManage, ordersResult }: OrderSectionsProps) {
  // Rendered per page load so form retries and double submits reuse one key;
  // the backend resolves a repeated key to the same stored order.
  const idempotencyKey = crypto.randomUUID()
  return (
    <>
      <section className="panel" aria-labelledby="order-apply-heading">
        <h2 className="panel-title" id="order-apply-heading">
          申请订阅（线下付款）
        </h2>
        {canManage ? (
          <OrderRequestForm action={submitOrderAction} idempotencyKey={idempotencyKey} />
        ) : (
          <p className="field-hint">你没有提交订单申请的权限，请联系租户管理员。</p>
        )}
      </section>

      <section className="panel" aria-labelledby="orders-heading">
        <h2 className="panel-title" id="orders-heading">
          我的订单
        </h2>
        {ordersResult.kind !== "ok" ? (
          <p className="notice">订单数据暂时不可用，请稍后再试。</p>
        ) : ordersResult.orders.length === 0 ? (
          <p className="field-hint">暂无订单记录。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>套餐</th>
                <th>金额</th>
                <th>付款凭证号</th>
                <th>状态</th>
                <th>提交时间</th>
                <th>审核备注</th>
              </tr>
            </thead>
            <tbody>
              {ordersResult.orders.map((order) => (
                <tr key={order.id}>
                  <td>
                    {order.plan_code} v{order.plan_version}
                  </td>
                  <td>{formatAmountCents(order.amount_cents)}</td>
                  <td>{order.payment_reference}</td>
                  <td>
                    <span className={order.status === "pending" ? "tag" : "tag tag-muted"}>
                      {orderStatusLabels[order.status]}
                    </span>
                  </td>
                  <td>{formatDateTime(order.created_at)}</td>
                  <td>{order.review_note === "" ? "—" : order.review_note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
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

  const [result, ordersResult] = await Promise.all([
    loadBillingSummary(createBillingTransport(), session),
    listOrders(createOrdersTransport(), session),
  ])

  if (result.kind === "mfaRequired" || ordersResult.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  const canManage = auth.view.permissions.includes("billing:manage")

  if (result.kind === "notFound") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">用量与套餐</h1>
          <p className="notice">当前租户暂无订阅</p>
        </section>
        <OrderSections canManage={canManage} ordersResult={ordersResult} />
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
  const isReadOnly =
    summary.status === "expired" ||
    summary.status === "cancelled" ||
    Date.parse(summary.current_period_end) <= Date.now()
  const canCancel =
    !isReadOnly &&
    (summary.status === "active" || summary.status === "trialing") &&
    !summary.cancel_requested_at &&
    canManage

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="plan-heading">
        <h1 className="panel-title" id="plan-heading">
          用量与套餐
        </h1>
        {isReadOnly ? <ReadOnlyBanner /> : null}
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
        {summary.cancel_requested_at ? (
          <p>
            已于 {formatDateTime(summary.cancel_requested_at)} 申请取消，将于{" "}
            {formatDateTime(summary.current_period_end)} 到期后取消。
          </p>
        ) : null}
        {canCancel ? <CancelSubscriptionAction action={cancelSubscriptionAction} /> : null}
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

      <OrderSections canManage={canManage} ordersResult={ordersResult} />
    </main>
  )
}
