import type { Metadata } from "next"
import Link from "next/link"

import { loginAction } from "@/app/actions/auth"
import { LoginForm } from "@/components/login-form"
import { Card } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "登录 · Relationship Network",
}

type LoginPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams
  const showMfaExpired = params["error"] === "mfa_challenge"

  return (
    <main className="auth-shell">
      <Card className="auth-card">
        <p className="eyebrow">ACCOUNT / 账户</p>
        <h1 className="auth-title">登录</h1>
        {showMfaExpired ? (
          <p className="form-error" role="alert">
            两步验证会话已过期，请重新登录
          </p>
        ) : null}
        <LoginForm action={loginAction} />
        <p className="auth-switch">
          还没有账户？<Link href="/register">立即注册</Link>
        </p>
        <p className="auth-switch">
          <Link href="/">返回首页</Link>
        </p>
      </Card>
    </main>
  )
}
