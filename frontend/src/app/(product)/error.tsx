"use client"

import Link from "next/link"

import {
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { Button, buttonVariants } from "@/components/ui/button"

export default function ProductError({ reset }: { readonly reset: () => void }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>页面出错了</PageTitle>
          <PageDescription>
            渲染此页面时发生意外错误。可以重试，或返回平台健康状态页。
          </PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={reset} type="button">
          重试
        </Button>
        <Link className={buttonVariants({ variant: "outline" })} href="/">
          返回首页
        </Link>
      </div>
    </Page>
  )
}
