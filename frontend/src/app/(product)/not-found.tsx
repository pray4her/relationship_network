import Link from "next/link"

import {
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { buttonVariants } from "@/components/ui/button"

export default function ProductNotFound() {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>页面不存在</PageTitle>
          <PageDescription>你要访问的页面不存在或已被移动。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <div>
        <Link className={buttonVariants({ variant: "outline" })} href="/">
          返回首页
        </Link>
      </div>
    </Page>
  )
}
