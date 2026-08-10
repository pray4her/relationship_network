import type { Metadata } from "next"
import Link from "next/link"

import { registerAction } from "@/app/actions/auth"
import { RegisterForm } from "@/components/register-form"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "注册",
}

export default function RegisterPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            ACCOUNT / 账户
          </p>
          <h1 className="text-2xl font-bold tracking-tight">注册</h1>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <RegisterForm action={registerAction} />
          <p className="text-sm text-muted-foreground">
            已有账户？
            <Link
              className="font-medium text-foreground underline underline-offset-4"
              href="/login"
            >
              直接登录
            </Link>
          </p>
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
