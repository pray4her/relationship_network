"use client"

import Link from "next/link"

import {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
} from "@/components/layout/page"
import { Button } from "@/components/ui/button"

export default function AuthError({ reset }: { readonly reset: () => void }) {
  return (
    <AuthPanel>
      <AuthPanelHeader>
        <AuthPanelTitle>页面出错了</AuthPanelTitle>
        <AuthPanelDescription>渲染此页面时发生意外错误，请重试。</AuthPanelDescription>
      </AuthPanelHeader>
      <AuthPanelContent>
        <Button onClick={reset} type="button">
          重试
        </Button>
      </AuthPanelContent>
      <AuthPanelFooter>
        <Link className="underline underline-offset-4" href="/">
          返回首页
        </Link>
      </AuthPanelFooter>
    </AuthPanel>
  )
}
