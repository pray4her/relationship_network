import Link from "next/link"
import type { ReactNode } from "react"

import { AccountPanel } from "@/components/account-panel"
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
    <main className="page-shell">
      <AccountPanel />
      <section className="panel">
        <h1 className="panel-title">{title}</h1>
        <p className="notice">{message ?? defaultMessage(failure)}</p>
        {children}
      </section>
    </main>
  )
}
