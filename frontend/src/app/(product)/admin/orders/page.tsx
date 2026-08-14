import { ArrowLeftIcon, SearchXIcon } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { confirmOrderAction, rejectOrderAction } from "@/app/actions/admin"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { adminTableHeadClassName, OrderStatusBadge } from "@/components/admin/admin-status-badges"
import { FilterSelect } from "@/components/admin/filter-select"
import { OrderReviewAction } from "@/components/admin/order-review-action"
import {
  DataRegion,
  DataRegionContent,
  DataRegionHeader,
  Page,
  PageActions,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
  PageToolbar,
} from "@/components/layout/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
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
import { formatDateTime } from "@/lib/format"
import { orderStatusSchema } from "@/lib/orders-contract"
import { formatAmountCents } from "@/lib/orders-view"

export const metadata: Metadata = {
  title: "订单审核",
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
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理</PageEyebrow>
          <PageTitle>订单审核</PageTitle>
          <PageDescription>审核租户提交的线下套餐订单。</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Button render={<Link href="/admin" />} variant="secondary">
            <ArrowLeftIcon /> 返回平台管理
          </Button>
        </PageActions>
      </PageHeader>

      <PageSection aria-labelledby="orders-list-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="orders-list-heading">订单列表</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <PageToolbar render={<form action="/admin/orders" method="get" />}>
          <Field className="w-full sm:w-48">
            <FieldLabel htmlFor="order-status">状态</FieldLabel>
            <FilterSelect defaultValue={status ?? ""} id="order-status" name="status">
              <option value="">全部</option>
              <option value="pending">待确认</option>
              <option value="confirmed">已确认</option>
              <option value="rejected">已拒绝</option>
            </FilterSelect>
          </Field>
          <Button type="submit" variant="secondary">
            筛选
          </Button>
          <Button render={<Link href="/admin/orders" />} variant="ghost">
            清除
          </Button>
        </PageToolbar>
        <DataRegion>
          <DataRegionHeader>
            <p className="m-0 font-medium text-foreground">筛选结果</p>
            <Badge variant="outline">共 {result.orders.length} 个订单</Badge>
          </DataRegionHeader>
          <DataRegionContent>
            {result.orders.length === 0 ? (
              <Empty>
                <EmptyMedia>
                  <SearchXIcon />
                </EmptyMedia>
                <EmptyHeader>
                  <EmptyTitle>没有符合条件的订单</EmptyTitle>
                  <EmptyDescription>调整筛选条件后再试。</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={`${adminTableHeadClassName} max-md:hidden`}>
                      租户 ID
                    </TableHead>
                    <TableHead className={adminTableHeadClassName}>套餐</TableHead>
                    <TableHead className={adminTableHeadClassName} numeric>
                      金额
                    </TableHead>
                    <TableHead className={`${adminTableHeadClassName} max-md:hidden`}>
                      付款凭证号
                    </TableHead>
                    <TableHead className={adminTableHeadClassName}>状态</TableHead>
                    <TableHead className={adminTableHeadClassName}>提交时间</TableHead>
                    <TableHead className={adminTableHeadClassName}>审核时间</TableHead>
                    <TableHead className={adminTableHeadClassName}>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.orders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell
                        className="max-w-40 truncate max-md:hidden"
                        title={order.tenant_id}
                      >
                        {order.tenant_id}
                      </TableCell>
                      <TableCell>
                        {order.plan_code} v{order.plan_version}
                      </TableCell>
                      <TableCell numeric>{formatAmountCents(order.amount_cents)}</TableCell>
                      <TableCell className="max-md:hidden">{order.payment_reference}</TableCell>
                      <TableCell>
                        <OrderStatusBadge status={order.status} />
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatDateTime(order.created_at)}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {order.reviewed_at === null ? "—" : formatDateTime(order.reviewed_at)}
                      </TableCell>
                      <TableCell>
                        {order.status === "pending" ? (
                          <OrderReviewAction
                            confirmAction={confirmOrderAction}
                            orderId={order.id}
                            rejectAction={rejectOrderAction}
                          />
                        ) : (
                          "—"
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
