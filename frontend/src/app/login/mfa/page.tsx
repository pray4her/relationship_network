import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { mfaVerifyAction } from "@/app/actions/auth"
import { MfaVerifyForm } from "@/components/mfa-verify-form"
import { Card } from "@/components/ui/card"
import { MFA_CHALLENGE_COOKIE_NAME } from "@/lib/auth-client"

export const metadata: Metadata = {
  title: "两步验证 · Relationship Network",
}

export default async function MfaLoginPage() {
  const store = await cookies()
  const challenge = store.get(MFA_CHALLENGE_COOKIE_NAME)?.value
  if (!challenge) {
    redirect("/login?error=mfa_challenge")
  }

  return (
    <main className="auth-shell">
      <Card className="auth-card">
        <p className="eyebrow">ACCOUNT / 账户</p>
        <h1 className="auth-title">两步验证</h1>
        <p className="auth-switch">该账户已启用 MFA，请完成第二步验证。</p>
        <MfaVerifyForm action={mfaVerifyAction} />
        <p className="auth-switch">
          <Link href="/login">返回登录</Link>
        </p>
      </Card>
    </main>
  )
}
