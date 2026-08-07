import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { redirect } from "next/navigation"

import { mfaVerifyAction } from "@/app/actions/auth"
import { MfaVerifyForm } from "@/components/mfa-verify-form"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
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
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            ACCOUNT / 账户
          </p>
          <h1 className="text-2xl font-bold tracking-tight">两步验证</h1>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">该账户已启用 MFA，请完成第二步验证。</p>
          <MfaVerifyForm action={mfaVerifyAction} />
          <p className="text-sm text-muted-foreground">
            <Link
              className="font-medium text-foreground underline underline-offset-4"
              href="/login"
            >
              返回登录
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}
