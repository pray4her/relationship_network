import { cookies } from "next/headers"
import Link from "next/link"

import { logoutAction } from "@/app/actions/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { WorkspaceNav } from "@/components/workspace-nav"
import {
  createAuthTransport,
  loadAuthSession,
  loadCurrentTenant,
  SESSION_COOKIE_NAME,
} from "@/lib/auth-client"

export async function AccountPanel() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  const transport = createAuthTransport()
  const auth = session
    ? await loadAuthSession(transport, session)
    : ({ kind: "anonymous" } as const)

  if (auth.kind !== "authenticated") {
    return (
      <section
        aria-label="账户"
        className="mx-auto flex w-full max-w-7xl items-center justify-between gap-6 px-6 pt-5"
      >
        <span className="text-sm text-muted-foreground">登录后可查看你的租户与资料</span>
        <nav className="flex gap-2">
          <Link className={buttonVariants({ variant: "outline" })} href="/login">
            登录
          </Link>
          <Link className={buttonVariants()} href="/register">
            注册
          </Link>
        </nav>
      </section>
    )
  }

  const tenant = session ? await loadCurrentTenant(transport, session) : null
  const mfaGateActive = tenant?.kind === "mfaRequired"

  return (
    <header className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-6 pt-5">
      <section
        aria-label="账户"
        className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3"
      >
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
            当前用户
          </span>
          <strong className="font-semibold">{auth.view.user.display_name}</strong>
          <span className="text-sm text-muted-foreground">{auth.view.user.email}</span>
        </div>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
            租户
          </span>
          {auth.view.tenant === null ? (
            <strong className="font-semibold">
              {auth.view.user.is_platform_admin ? "平台管理员（无租户）" : "无租户"}
            </strong>
          ) : (
            <>
              <strong className="font-semibold">{auth.view.tenant.name}</strong>
              <span className="text-sm text-muted-foreground">
                角色：{auth.view.role === "owner" ? "租户所有者" : "成员"}
              </span>
            </>
          )}
        </div>
        <form action={logoutAction}>
          <Button type="submit" variant="outline">
            退出登录
          </Button>
        </form>
      </section>
      <WorkspaceNav
        isPlatformAdmin={auth.view.user.is_platform_admin}
        permissions={auth.view.permissions}
      />
      {mfaGateActive ? (
        <Alert variant="destructive">
          <AlertDescription>
            租户已启用强制 MFA，请完成两步验证设置。
            <Link className="font-medium underline underline-offset-4" href="/settings/security">
              前往安全设置
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}
    </header>
  )
}
