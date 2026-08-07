import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { cancelSubscriptionAction, submitOrderAction } from "@/app/actions/orders"
import { AccountPanel } from "@/components/account-panel"
import { CancelSubscriptionAction } from "@/components/billing/cancel-subscription-action"
import { OrderRequestForm } from "@/components/billing/order-request-form"
import { ReadOnlyBanner } from "@/components/billing/read-only-banner"
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

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function NoticeCard({ children }: { readonly children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight">用量与套餐</h1>
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
      <Card aria-labelledby="order-apply-heading">
        <CardHeader>
          <h2 className="text-lg font-semibold" id="order-apply-heading">
            申请订阅（线下付款）
          </h2>
        </CardHeader>
        <CardContent>
          {canManage ? (
            <OrderRequestForm action={submitOrderAction} idempotencyKey={idempotencyKey} />
          ) : (
            <p className="text-sm text-muted-foreground">
              你没有提交订单申请的权限，请联系租户管理员。
            </p>
          )}
        </CardContent>
      </Card>

      <Card aria-labelledby="orders-heading">
        <CardHeader>
          <h2 className="text-lg font-semibold" id="orders-heading">
            我的订单
          </h2>
        </CardHeader>
        <CardContent>
          {ordersResult.kind !== "ok" ? (
            <p className="text-sm text-muted-foreground">订单数据暂时不可用，请稍后再试。</p>
          ) : ordersResult.orders.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无订单记录。</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className={headClassName}>套餐</TableHead>
                  <TableHead className={headClassName}>金额</TableHead>
                  <TableHead className={headClassName}>付款凭证号</TableHead>
                  <TableHead className={headClassName}>状态</TableHead>
                  <TableHead className={headClassName}>提交时间</TableHead>
                  <TableHead className={headClassName}>审核备注</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ordersResult.orders.map((order) => (
                  <TableRow key={order.id}>
                    <TableCell>
                      {order.plan_code} v{order.plan_version}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {formatAmountCents(order.amount_cents)}
                    </TableCell>
                    <TableCell>{order.payment_reference}</TableCell>
                    <TableCell>
                      <Badge variant={order.status === "pending" ? "default" : "secondary"}>
                        {orderStatusLabels[order.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {formatDateTime(order.created_at)}
                    </TableCell>
                    <TableCell>{order.review_note === "" ? "—" : order.review_note}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  )
}

export default async function UsagePage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticeCard>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
          登录
        </Link>
        后查看用量与套餐。
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
            <Link className="font-medium underline underline-offset-4" href="/login">
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

  if (auth.view.tenant === null) {
    return <NoticeCard>你没有加入任何租户，无法查看用量与套餐。</NoticeCard>
  }

  if (!auth.view.permissions.includes("billing:read")) {
    return <NoticeCard>你没有查看用量与套餐的权限。</NoticeCard>
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
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
        <AccountPanel />
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold tracking-tight">用量与套餐</h1>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertDescription>当前租户暂无订阅</AlertDescription>
            </Alert>
          </CardContent>
        </Card>
        <OrderSections canManage={canManage} ordersResult={ordersResult} />
      </main>
    )
  }

  if (result.kind !== "ok") {
    return <NoticeCard>用量数据暂时不可用，请稍后再试。</NoticeCard>
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
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />

      <Card aria-labelledby="plan-heading">
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight" id="plan-heading">
            用量与套餐
          </h1>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {isReadOnly ? <ReadOnlyBanner /> : null}
          <p>
            当前套餐：{summary.plan.name} v{summary.plan.version}{" "}
            <Badge variant="default">{billingStatusLabels[summary.status]}</Badge>
          </p>
          {summary.status === "trialing" && summary.trial_ends_at !== null ? (
            <p className="tabular-nums">试用到期时间：{formatDateTime(summary.trial_ends_at)}</p>
          ) : null}
          <p className="tabular-nums">
            当前计费周期：{formatDateTime(summary.current_period_start)} –{" "}
            {formatDateTime(summary.current_period_end)}
          </p>
          {summary.cancel_requested_at ? (
            <p className="tabular-nums">
              已于 {formatDateTime(summary.cancel_requested_at)} 申请取消，将于{" "}
              {formatDateTime(summary.current_period_end)} 到期后取消。
            </p>
          ) : null}
          {canCancel ? <CancelSubscriptionAction action={cancelSubscriptionAction} /> : null}
        </CardContent>
      </Card>

      <Card aria-labelledby="metrics-heading">
        <CardHeader>
          <h2 className="text-lg font-semibold" id="metrics-heading">
            配额用量
          </h2>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className={headClassName}>指标</TableHead>
                <TableHead className={headClassName}>限额</TableHead>
                <TableHead className={headClassName}>已用</TableHead>
                <TableHead className={headClassName}>预占中</TableHead>
                <TableHead className={headClassName}>剩余</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summary.metrics.map((metric) => (
                <TableRow key={metric.metric}>
                  <TableCell>{billingMetricLabels[metric.metric]}</TableCell>
                  <TableCell className="tabular-nums">{metric.limit}</TableCell>
                  <TableCell className="tabular-nums">{metric.used}</TableCell>
                  <TableCell className="tabular-nums">{metric.reserved}</TableCell>
                  <TableCell className="tabular-nums">{metric.remaining}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <OrderSections canManage={canManage} ordersResult={ordersResult} />
    </main>
  )
}
