import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

import {
  disableMfaAction,
  enableMfaAction,
  startMfaSetupAction,
  tenantMfaPolicyAction,
} from "@/app/actions/mfa"
import {
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { MfaDisableForm } from "@/components/security/mfa-disable-form"
import { MfaSetupWizard } from "@/components/security/mfa-setup-wizard"
import { TenantMfaPolicyForm } from "@/components/security/tenant-mfa-policy-form"
import { StatusBadge } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createMfaTransport, loadMfaStatus } from "@/lib/mfa-client"

export const metadata: Metadata = {
  title: "安全设置",
}

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>安全设置</PageTitle>
          <PageDescription>管理账户两步验证与租户安全策略。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

export default async function SecuritySettingsPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
          登录
        </Link>
        后管理安全设置。
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

  const status = await loadMfaStatus(createMfaTransport(), session)
  const canManageTenant = auth.view.permissions.includes("tenant:manage")

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>安全设置</PageTitle>
          <PageDescription>管理账户两步验证与租户安全策略。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <FormSection aria-labelledby="mfa-heading">
        <FormSectionHeader>
          <FormSectionTitle id="mfa-heading">两步验证（MFA）</FormSectionTitle>
          <FormSectionDescription>为当前账户配置身份验证器和恢复码。</FormSectionDescription>
        </FormSectionHeader>
        <FormSectionContent>
          {status.kind === "ok" ? (
            status.status.enabled ? (
              <div className="flex flex-col gap-4">
                <p className="flex flex-wrap items-center gap-2">
                  <StatusBadge label="已启用" tone="success" />
                  <span className="text-sm text-muted-foreground tabular-nums">
                    剩余恢复码 {status.status.recovery_codes_remaining} 个
                  </span>
                </p>
                <MfaDisableForm action={disableMfaAction} />
              </div>
            ) : (
              <MfaSetupWizard enableAction={enableMfaAction} startAction={startMfaSetupAction} />
            )
          ) : (
            <Alert>
              <AlertDescription>两步验证状态暂时不可用，请稍后再试。</AlertDescription>
            </Alert>
          )}
        </FormSectionContent>
      </FormSection>

      {canManageTenant ? (
        <FormSection aria-labelledby="policy-heading">
          <FormSectionHeader>
            <FormSectionTitle id="policy-heading">租户 MFA 策略</FormSectionTitle>
            <FormSectionDescription>
              要求租户成员完成两步验证后才能执行写操作。
            </FormSectionDescription>
          </FormSectionHeader>
          <FormSectionContent>
            <TenantMfaPolicyForm action={tenantMfaPolicyAction} />
          </FormSectionContent>
        </FormSection>
      ) : null}
    </Page>
  )
}
