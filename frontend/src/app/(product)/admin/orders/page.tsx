import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { confirmOrderAction, rejectOrderAction } from "@/app/actions/admin"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { OrderReviewAction } from "@/components/admin/order-review-action"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { createAdminTransport, listAdminOrders } from "@/lib/admin-client"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime } from "@/lib/admin-view"
import { orderStatusSchema } from "@/lib/orders-contract"
import { formatAmountCents, orderStatusLabels } from "@/lib/orders-view"

export const metadata: Metadata = {
  title: "订单审核",
}

type AdminOrdersPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

const selectClassName =
  "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

const tableHeadClassName = "font-mono text-xs tracking-wider text-muted-foreground uppercase"

function firstParam(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : ""
}

function OrderStatusBadge({ status }: { readonly status: keyof typeof orderStatusLabels }) {
  if (status === "confirmed") {
    return (
      <Badge className="bg-success/10 text-success" variant="secondary">
        {orderStatusLabels[status]}
      </Badge>
    )
  }
  if (status === "rejected") {
    return <Badge variant="destructive">{orderStatusLabels[status]}</Badge>
  }
  return <Badge variant="secondary">{orderStatusLabels[status]}</Badge>
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
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <section aria-labelledby="orders-heading">
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold tracking-tight" id="orders-heading">
              订单审核
            </h1>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <form action="/admin/orders" className="flex flex-wrap items-end gap-4" method="get">
              <Field className="w-full sm:w-48">
                <FieldLabel htmlFor="order-status">状态</FieldLabel>
                <select
                  className={selectClassName}
                  defaultValue={status ?? ""}
                  id="order-status"
                  name="status"
                >
                  <option value="">全部</option>
                  <option value="pending">待确认</option>
                  <option value="confirmed">已确认</option>
                  <option value="rejected">已拒绝</option>
                </select>
              </Field>
              <Button type="submit" variant="secondary">
                筛选
              </Button>
            </form>
            {result.orders.length === 0 ? (
              <p className="text-sm text-muted-foreground">没有符合条件的订单。</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={tableHeadClassName}>租户 ID</TableHead>
                    <TableHead className={tableHeadClassName}>套餐</TableHead>
                    <TableHead className={tableHeadClassName}>金额</TableHead>
                    <TableHead className={tableHeadClassName}>付款凭证号</TableHead>
                    <TableHead className={tableHeadClassName}>状态</TableHead>
                    <TableHead className={tableHeadClassName}>提交时间</TableHead>
                    <TableHead className={tableHeadClassName}>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.orders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell>{order.tenant_id}</TableCell>
                      <TableCell>
                        {order.plan_code} v{order.plan_version}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatAmountCents(order.amount_cents)}
                      </TableCell>
                      <TableCell>{order.payment_reference}</TableCell>
                      <TableCell>
                        <OrderStatusBadge status={order.status} />
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatDateTime(order.created_at)}
                      </TableCell>
                      <TableCell>
                        {order.status === "pending" ? (
                          <OrderReviewAction
                            confirmAction={confirmOrderAction}
                            orderId={order.id}
                            rejectAction={rejectOrderAction}
                          />
                        ) : order.reviewed_at === null ? (
                          "—"
                        ) : (
                          <span className="tabular-nums">{formatDateTime(order.reviewed_at)}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="text-sm text-muted-foreground">
              <Link className="font-medium underline underline-offset-4" href="/admin">
                返回平台管理
              </Link>
            </p>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
