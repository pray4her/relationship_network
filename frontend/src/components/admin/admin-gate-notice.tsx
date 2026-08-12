import Link from "next/link"
import type { ReactNode } from "react"

import {
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
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
          请先
          <Link className="font-medium underline underline-offset-4" href="/login">
            登录
          </Link>
          后访问平台管理控制台。
        </>
      )
    case "anonymous":
      return (
        <>
          登录已过期，请
          <Link className="font-medium underline underline-offset-4" href="/login">
            重新登录
          </Link>
          。
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
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle id="gate-heading">{title}</PageTitle>
          <PageDescription>平台管理入口。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert variant={failure === "forbidden" ? "destructive" : "default"}>
        <AlertDescription>{message ?? defaultMessage(failure)}</AlertDescription>
      </Alert>
      {children}
    </Page>
  )
}
