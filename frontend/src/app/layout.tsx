import type { Metadata } from "next"
import localFont from "next/font/local"
import type { ReactNode } from "react"

import "./globals.css"

const copernicus = localFont({
  display: "swap",
  src: "./fonts/CopernicusTrial-Book-BF66160450c2e92.ttf",
  variable: "--font-copernicus",
  weight: "400",
})

const styrene = localFont({
  display: "swap",
  src: [
    { path: "./fonts/StyreneB-Regular.otf", weight: "400" },
    { path: "./fonts/StyreneB-Medium.otf", weight: "500" },
  ],
  variable: "--font-styrene",
})

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
    <html className={`${copernicus.variable} ${styrene.variable}`} lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
