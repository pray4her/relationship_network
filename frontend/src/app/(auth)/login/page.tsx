import type { Metadata } from "next"
import Link from "next/link"

import { loginAction } from "@/app/actions/auth"
import {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
} from "@/components/layout/page"
import { LoginForm } from "@/components/login-form"
import { Alert, AlertDescription } from "@/components/ui/alert"

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
    <AuthPanel aria-labelledby="login-heading">
      <AuthPanelHeader>
        <AuthPanelTitle id="login-heading">登录</AuthPanelTitle>
        <AuthPanelDescription>使用成员账户进入租户。</AuthPanelDescription>
      </AuthPanelHeader>
      <AuthPanelContent>
        {showMfaExpired ? (
          <Alert variant="destructive">
            <AlertDescription>两步验证会话已过期，请重新登录。</AlertDescription>
          </Alert>
        ) : null}
        <LoginForm action={loginAction} />
      </AuthPanelContent>
      <AuthPanelFooter className="flex flex-col gap-3">
        <p className="m-0">
          还没有账户？
          <Link
            className="font-medium text-foreground underline underline-offset-4"
            href="/register"
          >
            立即注册
          </Link>
        </p>
        <p className="m-0">
          <Link className="font-medium text-foreground underline underline-offset-4" href="/">
            返回首页
          </Link>
        </p>
      </AuthPanelFooter>
    </AuthPanel>
  )
}
