import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { cancelSubscriptionAction, submitOrderAction } from "@/app/actions/orders"
import { billingStatusMeta, orderStatusMeta } from "@/components/billing/billing-status"
import { CancelSubscriptionAction } from "@/components/billing/cancel-subscription-action"
import { OrderRequestForm } from "@/components/billing/order-request-form"
import { ReadOnlyBanner } from "@/components/billing/read-only-banner"
import {
  DataRegion,
  DataRegionContent,
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { StatusBadge } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
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
import type { BillingMetric } from "@/lib/billing-contract"
import { formatDateTime } from "@/lib/format"
import { createOrdersTransport, listOrders, type OrderListResult } from "@/lib/orders-client"
import { formatAmountCents } from "@/lib/orders-view"

export const metadata: Metadata = {
  title: "用量与套餐",
}

const billingMetricLabels: Record<BillingMetric, string> = {
  active_jobs: "活跃职位",
  companies: "企业",
  matches: "匹配次数",
  owners: "所有者",
  reports: "报告份数",
  searches: "搜索次数",
}

const headClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>用量与套餐</PageTitle>
          <PageDescription>查看套餐状态、配额使用与订单记录。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
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
      <FormSection aria-labelledby="order-apply-heading">
        <FormSectionHeader>
          <FormSectionTitle id="order-apply-heading">申请订阅（线下付款）</FormSectionTitle>
          <FormSectionDescription>提交套餐与付款凭证，等待平台管理员审核。</FormSectionDescription>
        </FormSectionHeader>
        <FormSectionContent>
          {canManage ? (
            <OrderRequestForm action={submitOrderAction} idempotencyKey={idempotencyKey} />
          ) : (
            <p className="text-sm text-muted-foreground">
              你没有提交订单申请的权限，请联系租户管理员。
            </p>
          )}
        </FormSectionContent>
      </FormSection>

      <PageSection aria-labelledby="orders-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="orders-heading">我的订单</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {ordersResult.kind !== "ok" ? (
              <p className="text-sm text-muted-foreground">订单数据暂时不可用，请稍后再试。</p>
            ) : ordersResult.orders.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>暂无订单记录</EmptyTitle>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={headClassName}>套餐</TableHead>
                    <TableHead className={headClassName} numeric>
                      金额
                    </TableHead>
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
                      <TableCell numeric>{formatAmountCents(order.amount_cents)}</TableCell>
                      <TableCell>{order.payment_reference}</TableCell>
                      <TableCell>
                        <StatusBadge {...orderStatusMeta[order.status]} />
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
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </>
  )
}

export default async function UsagePage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
          登录
        </Link>
        后查看用量与套餐。
      </NoticePage>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <NoticePage>
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
      </NoticePage>
    )
  }

  if (auth.view.tenant === null) {
    return <NoticePage>你没有加入任何租户，无法查看用量与套餐。</NoticePage>
  }

  if (!auth.view.permissions.includes("billing:read")) {
    return <NoticePage>你没有查看用量与套餐的权限。</NoticePage>
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
      <Page>
        <PageHeader>
          <PageHeaderContent>
            <PageTitle>用量与套餐</PageTitle>
            <PageDescription>查看套餐状态、配额使用与订单记录。</PageDescription>
          </PageHeaderContent>
        </PageHeader>
        <Alert>
          <AlertDescription>当前租户暂无订阅</AlertDescription>
        </Alert>
        <OrderSections canManage={canManage} ordersResult={ordersResult} />
      </Page>
    )
  }

  if (result.kind !== "ok") {
    return <NoticePage>用量数据暂时不可用，请稍后再试。</NoticePage>
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
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle id="plan-heading">用量与套餐</PageTitle>
          <PageDescription>查看套餐状态、配额使用与订单记录。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <PageSection aria-labelledby="summary-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="summary-heading">套餐概况</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent className="flex flex-col gap-3 p-5">
            {isReadOnly ? <ReadOnlyBanner /> : null}
            <p>
              当前套餐：{summary.plan.name} v{summary.plan.version}{" "}
              <StatusBadge {...billingStatusMeta[summary.status]} />
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
          </DataRegionContent>
        </DataRegion>
      </PageSection>

      <PageSection aria-labelledby="metrics-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="metrics-heading">配额用量</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent>
            {summary.metrics.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>暂无配额数据</EmptyTitle>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={headClassName}>指标</TableHead>
                    <TableHead className={headClassName} numeric>
                      限额
                    </TableHead>
                    <TableHead className={headClassName} numeric>
                      已用
                    </TableHead>
                    <TableHead className={headClassName} numeric>
                      预占中
                    </TableHead>
                    <TableHead className={headClassName} numeric>
                      剩余
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.metrics.map((metric) => (
                    <TableRow key={metric.metric}>
                      <TableCell>{billingMetricLabels[metric.metric]}</TableCell>
                      <TableCell numeric>{metric.limit}</TableCell>
                      <TableCell numeric>{metric.used}</TableCell>
                      <TableCell numeric>{metric.reserved}</TableCell>
                      <TableCell numeric>{metric.remaining}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </DataRegionContent>
        </DataRegion>
      </PageSection>

      <OrderSections canManage={canManage} ordersResult={ordersResult} />
    </Page>
  )
}
