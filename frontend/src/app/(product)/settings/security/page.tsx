import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

import {
  disableMfaAction,
  enableMfaAction,
  startMfaSetupAction,
  tenantMfaPolicyAction,
} from "@/app/actions/mfa"
import { MfaDisableForm } from "@/components/security/mfa-disable-form"
import { MfaSetupWizard } from "@/components/security/mfa-setup-wizard"
import { TenantMfaPolicyForm } from "@/components/security/tenant-mfa-policy-form"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createMfaTransport, loadMfaStatus } from "@/lib/mfa-client"

export const metadata: Metadata = {
  title: "安全设置",
}

export default async function SecuritySettingsPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold tracking-tight">安全设置</h1>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertDescription>
                请先
                <Link className="font-medium underline underline-offset-4" href="/login">
                  登录
                </Link>
                后管理安全设置。
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      </main>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold tracking-tight">安全设置</h1>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertDescription>
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
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      </main>
    )
  }

  const status = await loadMfaStatus(createMfaTransport(), session)
  const canManageTenant = auth.view.permissions.includes("tenant:manage")

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <Card aria-labelledby="mfa-heading">
        <CardHeader>
          <h1 className="text-2xl font-bold tracking-tight" id="mfa-heading">
            两步验证（MFA）
          </h1>
        </CardHeader>
        <CardContent>
          {status.kind === "ok" ? (
            status.status.enabled ? (
              <div className="flex flex-col gap-4">
                <p className="flex flex-wrap items-center gap-2">
                  <Badge className="bg-success/10 text-success">已启用</Badge>
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
        </CardContent>
      </Card>

      {canManageTenant ? (
        <Card aria-labelledby="policy-heading">
          <CardHeader>
            <h2 className="text-lg font-semibold" id="policy-heading">
              租户 MFA 策略
            </h2>
          </CardHeader>
          <CardContent>
            <TenantMfaPolicyForm action={tenantMfaPolicyAction} />
          </CardContent>
        </Card>
      ) : null}
    </main>
  )
}
