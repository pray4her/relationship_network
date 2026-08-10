import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { mfaVerifyAction } from "@/app/actions/auth"
import {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
} from "@/components/layout/page"
import { MfaVerifyForm } from "@/components/mfa-verify-form"
import { MFA_CHALLENGE_COOKIE_NAME } from "@/lib/auth-client"

export const metadata: Metadata = {
  title: "两步验证",
}

export default async function MfaLoginPage() {
  const store = await cookies()
  const challenge = store.get(MFA_CHALLENGE_COOKIE_NAME)?.value
  if (!challenge) {
    redirect("/login?error=mfa_challenge")
  }

  return (
    <AuthPanel aria-labelledby="mfa-login-heading">
      <AuthPanelHeader>
        <AuthPanelTitle id="mfa-login-heading">两步验证</AuthPanelTitle>
        <AuthPanelDescription>该账户已启用两步验证，请完成第二步验证。</AuthPanelDescription>
      </AuthPanelHeader>
      <AuthPanelContent>
        <MfaVerifyForm action={mfaVerifyAction} />
      </AuthPanelContent>
      <AuthPanelFooter>
        <Link className="font-medium text-foreground underline underline-offset-4" href="/login">
          返回登录
        </Link>
      </AuthPanelFooter>
    </AuthPanel>
  )
}
