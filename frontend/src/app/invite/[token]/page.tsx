import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

import { registerAction } from "@/app/actions/auth"
import { acceptInvitationAction } from "@/app/actions/invitations"
import { AcceptInviteForm } from "@/components/accept-invite-form"
import { InviteRegisterForm } from "@/components/invite-register-form"
import { Card } from "@/components/ui/card"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createInvitationsTransport, previewInvitation } from "@/lib/invitations-client"

export const metadata: Metadata = {
  title: "接受邀请 · Relationship Network",
}

type InvitePageProps = {
  readonly params: Promise<{ readonly token: string }>
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

export default async function InvitePage({ params }: InvitePageProps) {
  const { token } = await params
  const preview = await previewInvitation(createInvitationsTransport(), token)

  if (preview.kind !== "ok") {
    return (
      <main className="auth-shell">
        <Card className="auth-card">
          <p className="eyebrow">INVITE / 邀请</p>
          <h1 className="auth-title">邀请无效</h1>
          <p className="notice" role="alert">
            {preview.kind === "invalid"
              ? "邀请链接无效、已被撤销或已过期，请联系邀请人重新发送。"
              : "服务暂时不可用，请稍后再试。"}
          </p>
          <p className="auth-switch">
            <Link href="/">返回首页</Link>
          </p>
        </Card>
      </main>
    )
  }

  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  const auth = session
    ? await loadAuthSession(createAuthTransport(), session)
    : ({ kind: "anonymous" } as const)

  return (
    <main className="auth-shell">
      <Card className="auth-card">
        <p className="eyebrow">INVITE / 邀请</p>
        <h1 className="auth-title">加入 {preview.preview.tenant_name}</h1>
        <p className="auth-switch">
          邀请邮箱：{preview.preview.email} · 有效期至 {formatDateTime(preview.preview.expires_at)}
        </p>

        {auth.kind === "authenticated" ? (
          <>
            <p className="field-hint">
              当前登录账号：{auth.view.user.email}（{auth.view.user.display_name}）
            </p>
            <AcceptInviteForm action={acceptInvitationAction} token={token} />
          </>
        ) : (
          <>
            <InviteRegisterForm
              action={registerAction}
              email={preview.preview.email}
              inviteToken={token}
              tenantName={preview.preview.tenant_name}
            />
            <p className="auth-switch">
              已有账号？<Link href="/login">登录后重新打开本邀请链接</Link>
            </p>
          </>
        )}

        <p className="auth-switch">
          <Link href="/">返回首页</Link>
        </p>
      </Card>
    </main>
  )
}
