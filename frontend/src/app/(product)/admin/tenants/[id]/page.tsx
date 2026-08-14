import { ArrowLeftIcon } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { tenantStatusAction } from "@/app/actions/admin"
import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { TenantStatusBadge } from "@/components/admin/admin-status-badges"
import { TenantStatusAction } from "@/components/admin/tenant-status-action"
import {
  DescriptionDetails,
  DescriptionItem,
  DescriptionList,
  DescriptionTerm,
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
} from "@/components/layout/page"
import { Button } from "@/components/ui/button"
import { createAdminTransport, loadAdminTenant } from "@/lib/admin-client"
import { requireAdminView } from "@/lib/admin-guard"
import { formatDateTime } from "@/lib/format"

export const metadata: Metadata = {
  title: "租户详情",
}

type AdminTenantPageProps = {
  readonly params: Promise<{ id: string }>
}

const linkClassName = "font-medium underline underline-offset-4"

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
        <p className="m-0 text-sm text-muted-foreground">
          <Link className={linkClassName} href="/admin">
            返回租户列表
          </Link>
        </p>
      </AdminGateNotice>
    )
  }

  const tenant = result.tenant

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理</PageEyebrow>
          <PageTitle>{tenant.name}</PageTitle>
          <PageDescription>查看租户状态并执行暂停或恢复操作。</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Button render={<Link href="/admin" />} variant="secondary">
            <ArrowLeftIcon /> 返回租户列表
          </Button>
        </PageActions>
      </PageHeader>

      <PageSection aria-labelledby="tenant-facts-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="tenant-facts-heading">租户信息</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DescriptionList>
          <DescriptionItem>
            <DescriptionTerm>标识</DescriptionTerm>
            <DescriptionDetails>{tenant.slug}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>状态</DescriptionTerm>
            <DescriptionDetails>
              <TenantStatusBadge status={tenant.status} />
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>强制两步验证</DescriptionTerm>
            <DescriptionDetails>{tenant.mfa_required ? "已开启" : "未开启"}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>成员数</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">{tenant.member_count}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>创建时间</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {formatDateTime(tenant.created_at)}
            </DescriptionDetails>
          </DescriptionItem>
        </DescriptionList>
        <TenantStatusAction
          action={tenantStatusAction}
          status={tenant.status}
          tenantId={tenant.id}
        />
      </PageSection>
    </Page>
  )
}
