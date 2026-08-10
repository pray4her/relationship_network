import type { Metadata } from "next"
import Link from "next/link"

import { registerAction } from "@/app/actions/auth"
import {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
} from "@/components/layout/page"
import { RegisterForm } from "@/components/register-form"

export const metadata: Metadata = {
  title: "注册",
}

export default function RegisterPage() {
  return (
    <AuthPanel aria-labelledby="register-heading">
      <AuthPanelHeader>
        <AuthPanelTitle id="register-heading">注册</AuthPanelTitle>
        <AuthPanelDescription>创建成员账户和首个租户。</AuthPanelDescription>
      </AuthPanelHeader>
      <AuthPanelContent>
        <RegisterForm action={registerAction} />
      </AuthPanelContent>
      <AuthPanelFooter className="space-y-[var(--space-3)]">
        <p className="m-0">
          已有账户？
          <Link className="font-medium text-foreground underline underline-offset-4" href="/login">
            直接登录
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
