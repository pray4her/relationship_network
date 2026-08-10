import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

import { registerAction } from "@/app/actions/auth"
import { acceptInvitationAction } from "@/app/actions/invitations"
import { AcceptInviteForm } from "@/components/accept-invite-form"
import { InviteRegisterForm } from "@/components/invite-register-form"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createInvitationsTransport, previewInvitation } from "@/lib/invitations-client"

export const metadata: Metadata = {
  title: "接受邀请",
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
      <main className="flex min-h-dvh items-center justify-center px-4 py-10">
        <Card className="w-full max-w-md">
          <CardHeader>
            <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
              INVITE / 邀请
            </p>
            <h1 className="text-2xl font-bold tracking-tight">邀请无效</h1>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Alert variant="destructive">
              <AlertDescription>
                {preview.kind === "invalid"
                  ? "邀请链接无效、已被撤销或已过期，请联系邀请人重新发送。"
                  : "服务暂时不可用，请稍后再试。"}
              </AlertDescription>
            </Alert>
            <p className="text-sm text-muted-foreground">
              <Link className="font-medium text-foreground underline underline-offset-4" href="/">
                返回首页
              </Link>
            </p>
          </CardContent>
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
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            INVITE / 邀请
          </p>
          <h1 className="text-2xl font-bold tracking-tight">加入 {preview.preview.tenant_name}</h1>
          <p className="text-sm text-muted-foreground">
            邀请邮箱：{preview.preview.email} · 有效期至{" "}
            {formatDateTime(preview.preview.expires_at)}
          </p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {auth.kind === "authenticated" ? (
            <>
              <p className="text-sm text-muted-foreground">
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
              <p className="text-sm text-muted-foreground">
                已有账号？
                <Link
                  className="font-medium text-foreground underline underline-offset-4"
                  href="/login"
                >
                  登录后重新打开本邀请链接
                </Link>
              </p>
            </>
          )}

          <p className="text-sm text-muted-foreground">
            <Link className="font-medium text-foreground underline underline-offset-4" href="/">
              返回首页
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}
