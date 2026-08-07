import Link from "next/link"
import type { ReactNode } from "react"

import { AccountPanel } from "@/components/account-panel"
import { Alert, AlertDescription } from "@/components/ui/alert"
import type { AdminGateFailure } from "@/lib/admin-guard"

type AdminGateNoticeProps = {
  readonly failure: AdminGateFailure
  readonly title: string
  readonly message?: ReactNode
  readonly children?: ReactNode
}

function defaultMessage(failure: AdminGateFailure): ReactNode {
  switch (failure) {
    case "noSession":
      return (
        <>
          请先<Link href="/login">登录</Link>后访问平台管理控制台。
        </>
      )
    case "anonymous":
      return (
        <>
          登录已过期，请<Link href="/login">重新登录</Link>。
        </>
      )
    case "forbidden":
      return "你没有访问平台管理控制台的权限。"
    case "unreachable":
      return "服务暂时不可用，请稍后再试。"
  }
}

export function AdminGateNotice({ children, failure, message, title }: AdminGateNoticeProps) {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
      <AccountPanel />
      <section aria-labelledby="gate-heading" className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold tracking-tight" id="gate-heading">
          {title}
        </h1>
        <Alert variant={failure === "forbidden" ? "destructive" : "default"}>
          <AlertDescription>{message ?? defaultMessage(failure)}</AlertDescription>
        </Alert>
        {children}
      </section>
    </main>
  )
}
