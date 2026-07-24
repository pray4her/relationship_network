import type { Metadata } from "next"
import Link from "next/link"

import { loginAction } from "@/app/actions/auth"
import { LoginForm } from "@/components/login-form"
import { Card } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "登录 · Relationship Network",
}

export default function LoginPage() {
  return (
    <main className="auth-shell">
      <Card className="auth-card">
        <p className="eyebrow">ACCOUNT / 账户</p>
        <h1 className="auth-title">登录</h1>
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
