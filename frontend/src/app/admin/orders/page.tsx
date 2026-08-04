import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { confirmOrderAction, rejectOrderAction } from "@/app/actions/admin"
import { AccountPanel } from "@/components/account-panel"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { OrderReviewAction } from "@/components/admin/order-review-action"
import { Button } from "@/components/ui/button"
import { createAdminTransport, listAdminOrders } from "@/lib/admin-client"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime } from "@/lib/admin-view"
import { orderStatusSchema } from "@/lib/orders-contract"
import { formatAmountCents, orderStatusLabels } from "@/lib/orders-view"

export const metadata: Metadata = {
  title: "订单审核 · Relationship Network",
}

type AdminOrdersPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

function firstParam(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : ""
}

export default async function AdminOrdersPage({ searchParams }: AdminOrdersPageProps) {
  const params = await searchParams
  const parsedStatus = orderStatusSchema.safeParse(firstParam(params["status"]))
  const status = parsedStatus.success ? parsedStatus.data : null

  const guard = await requireAdminView()
  if (guard.kind !== "ok") {
    return <AdminGateNotice failure={guard.kind} title="订单审核" />
  }

  const result = await listAdminOrders(createAdminTransport(), guard.session, status)

  if (result.kind === "mfaRequired") {
    redirect("/settings/security")
  }

  if (result.kind === "anonymous" || result.kind === "forbidden") {
    return <AdminGateNotice failure={result.kind} title="订单审核" />
  }

  if (result.kind !== "ok") {
    return (
      <AdminGateNotice
        failure="unreachable"
        message="订单数据暂时不可用，请稍后再试。"
        title="订单审核"
      />
    )
  }

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="orders-heading">
        <h1 className="panel-title" id="orders-heading">
          订单审核
        </h1>
        <form action="/admin/orders" className="auth-form" method="get">
          <div className="form-field">
            <label className="field-label" htmlFor="order-status">
              状态
            </label>
            <select
              className="field-input"
              defaultValue={status ?? ""}
              id="order-status"
              name="status"
            >
              <option value="">全部</option>
              <option value="pending">待确认</option>
              <option value="confirmed">已确认</option>
              <option value="rejected">已拒绝</option>
            </select>
          </div>
          <div>
            <Button mode="secondary" type="submit">
              筛选
            </Button>
          </div>
        </form>
        {result.orders.length === 0 ? (
          <p className="field-hint">没有符合条件的订单。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>租户 ID</th>
                <th>套餐</th>
                <th>金额</th>
                <th>付款凭证号</th>
                <th>状态</th>
                <th>提交时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {result.orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.tenant_id}</td>
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
                  <td>
                    {order.status === "pending" ? (
                      <OrderReviewAction
                        confirmAction={confirmOrderAction}
                        orderId={order.id}
                        rejectAction={rejectOrderAction}
                      />
                    ) : order.reviewed_at === null ? (
                      "—"
                    ) : (
                      formatDateTime(order.reviewed_at)
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="field-hint">
          <Link href="/admin">返回平台管理</Link>
        </p>
      </section>
    </main>
  )
}
