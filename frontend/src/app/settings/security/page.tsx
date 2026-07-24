import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

import {
  disableMfaAction,
  enableMfaAction,
  startMfaSetupAction,
  tenantMfaPolicyAction,
} from "@/app/actions/mfa"
import { AccountPanel } from "@/components/account-panel"
import { MfaDisableForm } from "@/components/security/mfa-disable-form"
import { MfaSetupWizard } from "@/components/security/mfa-setup-wizard"
import { TenantMfaPolicyForm } from "@/components/security/tenant-mfa-policy-form"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createMfaTransport, loadMfaStatus } from "@/lib/mfa-client"

export const metadata: Metadata = {
  title: "安全设置 · Relationship Network",
}

export default async function SecuritySettingsPage() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">安全设置</h1>
          <p className="notice">
            请先<Link href="/login">登录</Link>后管理安全设置。
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
          <h1 className="panel-title">安全设置</h1>
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

  const status = await loadMfaStatus(createMfaTransport(), session)
  const canManageTenant = auth.view.permissions.includes("tenant:manage")

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="mfa-heading">
        <h1 className="panel-title" id="mfa-heading">
          两步验证（MFA）
        </h1>
        {status.kind === "ok" ? (
          status.status.enabled ? (
            <div className="mfa-step">
              <p>
                <span className="tag">已启用</span>{" "}
                <span className="field-hint">
                  剩余恢复码 {status.status.recovery_codes_remaining} 个
                </span>
              </p>
              <MfaDisableForm action={disableMfaAction} />
            </div>
          ) : (
            <MfaSetupWizard enableAction={enableMfaAction} startAction={startMfaSetupAction} />
          )
        ) : (
          <p className="notice">两步验证状态暂时不可用，请稍后再试。</p>
        )}
      </section>

      {canManageTenant ? (
        <section className="panel" aria-labelledby="policy-heading">
          <h2 className="panel-title" id="policy-heading">
            租户 MFA 策略
          </h2>
          <TenantMfaPolicyForm action={tenantMfaPolicyAction} />
        </section>
      ) : null}
    </main>
  )
}
