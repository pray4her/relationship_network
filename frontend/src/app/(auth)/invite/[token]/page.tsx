import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

import { registerAction } from "@/app/actions/auth"
import { acceptInvitationAction } from "@/app/actions/invitations"
import { AcceptInviteForm } from "@/components/accept-invite-form"
import { InviteRegisterForm } from "@/components/invite-register-form"
import {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
} from "@/components/layout/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
      <AuthPanel aria-labelledby="invalid-invite-heading">
        <AuthPanelHeader>
          <AuthPanelTitle id="invalid-invite-heading">邀请无效</AuthPanelTitle>
          <AuthPanelDescription>无法继续处理此邀请。</AuthPanelDescription>
        </AuthPanelHeader>
        <AuthPanelContent>
          <Alert variant="destructive">
            <AlertDescription>
              {preview.kind === "invalid"
                ? "邀请链接无效、已被撤销或已过期，请联系邀请人重新发送。"
                : "服务暂时不可用，请稍后再试。"}
            </AlertDescription>
          </Alert>
        </AuthPanelContent>
        <AuthPanelFooter>
          <Link className="font-medium text-foreground underline underline-offset-4" href="/">
            返回首页
          </Link>
        </AuthPanelFooter>
      </AuthPanel>
    )
  }

  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  const auth = session
    ? await loadAuthSession(createAuthTransport(), session)
    : ({ kind: "anonymous" } as const)

  return (
    <AuthPanel aria-labelledby="invite-heading">
      <AuthPanelHeader>
        <AuthPanelTitle id="invite-heading">加入 {preview.preview.tenant_name}</AuthPanelTitle>
        <AuthPanelDescription>
          邀请邮箱：{preview.preview.email}；有效期至 {formatDateTime(preview.preview.expires_at)}。
        </AuthPanelDescription>
      </AuthPanelHeader>
      <AuthPanelContent>
        {auth.kind === "authenticated" ? (
          <>
            <p className="m-0 text-sm text-muted-foreground">
              当前登录账户：{auth.view.user.email}（{auth.view.user.display_name}）
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
            <p className="m-0 text-sm text-muted-foreground">
              已有账户？
              <Link
                className="font-medium text-foreground underline underline-offset-4"
                href="/login"
              >
                登录后重新打开本邀请链接
              </Link>
            </p>
          </>
        )}
      </AuthPanelContent>
      <AuthPanelFooter>
        <Link className="font-medium text-foreground underline underline-offset-4" href="/">
          返回首页
        </Link>
      </AuthPanelFooter>
    </AuthPanel>
  )
}
