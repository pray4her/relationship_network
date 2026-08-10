import type { Metadata } from "next"
import Link from "next/link"

import { loginAction } from "@/app/actions/auth"
import { LoginForm } from "@/components/login-form"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "登录",
}

type LoginPageProps = {
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams
  const showMfaExpired = params["error"] === "mfa_challenge"

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            ACCOUNT / 账户
          </p>
          <h1 className="text-2xl font-bold tracking-tight">登录</h1>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {showMfaExpired ? (
            <Alert variant="destructive">
              <AlertDescription>两步验证会话已过期，请重新登录</AlertDescription>
            </Alert>
          ) : null}
          <LoginForm action={loginAction} />
          <p className="text-sm text-muted-foreground">
            还没有账户？
            <Link
              className="font-medium text-foreground underline underline-offset-4"
              href="/register"
            >
              立即注册
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
