import Link from "next/link"

import {
  AuthPanel,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
} from "@/components/layout/page"

export default function AuthNotFound() {
  return (
    <AuthPanel>
      <AuthPanelHeader>
        <AuthPanelTitle>页面不存在</AuthPanelTitle>
        <AuthPanelDescription>你要访问的页面不存在或已被移动。</AuthPanelDescription>
      </AuthPanelHeader>
      <AuthPanelFooter>
        <Link className="underline underline-offset-4" href="/">
          返回首页
        </Link>
      </AuthPanelFooter>
    </AuthPanel>
  )
}
