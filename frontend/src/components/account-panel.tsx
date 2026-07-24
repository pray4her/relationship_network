import { cookies } from "next/headers"
import Link from "next/link"

import { logoutAction } from "@/app/actions/auth"
import { Button } from "@/components/ui/button"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"

export async function AccountPanel() {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  const auth = session
    ? await loadAuthSession(createAuthTransport(), session)
    : ({ kind: "anonymous" } as const)

  if (auth.kind !== "authenticated") {
    return (
      <section className="account-bar" aria-label="账户">
        <span className="account-hint">登录后可查看你的租户与资料</span>
        <nav className="account-actions">
          <Link className="account-link" href="/login">
            登录
          </Link>
          <Link className="account-link account-link-strong" href="/register">
            注册
          </Link>
        </nav>
      </section>
    )
  }

  return (
    <section className="account-bar" aria-label="账户">
      <div className="account-identity">
        <span className="account-label">当前用户</span>
        <strong>{auth.view.user.display_name}</strong>
        <span className="account-email">{auth.view.user.email}</span>
      </div>
      <div className="account-tenant">
        <span className="account-label">租户</span>
        <strong>{auth.view.tenant.name}</strong>
        <span className="account-role">角色：租户所有者</span>
      </div>
      <form action={logoutAction}>
        <Button mode="secondary" type="submit">
          退出登录
        </Button>
      </form>
    </section>
  )
}
