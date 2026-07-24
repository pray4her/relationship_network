import type { Metadata } from "next"
import Link from "next/link"

import { registerAction } from "@/app/actions/auth"
import { RegisterForm } from "@/components/register-form"
import { Card } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "注册 · Relationship Network",
}

export default function RegisterPage() {
  return (
    <main className="auth-shell">
      <Card className="auth-card">
        <p className="eyebrow">ACCOUNT / 账户</p>
        <h1 className="auth-title">注册</h1>
        <RegisterForm action={registerAction} />
        <p className="auth-switch">
          已有账户？<Link href="/login">直接登录</Link>
        </p>
        <p className="auth-switch">
          <Link href="/">返回首页</Link>
        </p>
      </Card>
    </main>
  )
}
