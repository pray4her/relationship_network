import { cookies } from "next/headers"
import type { ReactNode } from "react"

import { AppNavbar, type AppNavbarAccount } from "@/components/layout/app-navbar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  createAuthTransport,
  loadAuthSession,
  loadCurrentTenant,
  SESSION_COOKIE_NAME,
} from "@/lib/auth-client"

type AppShellState = {
  readonly account: AppNavbarAccount | null
  readonly mfaGateActive: boolean
}

async function loadAppShellState(): Promise<AppShellState> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { account: null, mfaGateActive: false }
  }

  const transport = createAuthTransport()
  const [auth, tenant] = await Promise.all([
    loadAuthSession(transport, session),
    loadCurrentTenant(transport, session),
  ])

  if (auth.kind !== "authenticated") {
    return { account: null, mfaGateActive: false }
  }

  return {
    account: {
      displayName: auth.view.user.display_name,
      email: auth.view.user.email,
      isPlatformAdmin: auth.view.user.is_platform_admin,
      permissions: auth.view.permissions,
      role: auth.view.role,
      tenantName: auth.view.tenant?.name ?? null,
    },
    mfaGateActive: tenant.kind === "mfaRequired",
  }
}

export async function AppShell({ children }: { readonly children: ReactNode }) {
  const state = await loadAppShellState()

  return (
    <div className="min-h-dvh bg-background">
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:underline"
        href="#main-content"
      >
        跳到主内容
      </a>
      <AppNavbar account={state.account} />
      {state.mfaGateActive ? (
        <div className="mx-auto w-full max-w-[1400px] px-6 pt-4 max-sm:px-4">
          <Alert variant="destructive">
            <AlertDescription>
              租户已要求成员启用两步验证。请前往安全设置完成配置后再继续写入操作。
            </AlertDescription>
          </Alert>
        </div>
      ) : null}
      {children}
    </div>
  )
}
