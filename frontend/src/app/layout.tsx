import type { Metadata } from "next"
import type { ReactNode } from "react"

import { Toaster } from "@/components/ui/sonner"

import "./globals.css"

export const metadata: Metadata = {
  description: "全球人才精准匹配与租户协作平台",
  icons: { icon: "/icon.svg" },
  title: {
    default: "Relationship Network",
    template: "%s · Relationship Network",
  },
}

type RootLayoutProps = {
  readonly children: ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
        <Toaster position="top-center" />
      </body>
    </html>
  )
}
