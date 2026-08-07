import type { Metadata } from "next"
import localFont from "next/font/local"
import type { ReactNode } from "react"

import "./globals.css"

const anthropicSans = localFont({
  display: "swap",
  src: "./fonts/AnthropicSans-Variable.woff2",
  variable: "--font-anthropic-sans",
  weight: "300 800",
})

const anthropicMono = localFont({
  display: "swap",
  src: "./fonts/AnthropicMono-Variable.woff2",
  variable: "--font-anthropic-mono",
  weight: "300 800",
})

export const metadata: Metadata = {
  description: "全球人才精准匹配平台运行状态",
  title: "Relationship Network · 系统状态",
}

type RootLayoutProps = {
  readonly children: ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN">
      <body className={`${anthropicSans.variable} ${anthropicMono.variable}`}>{children}</body>
    </html>
  )
}
