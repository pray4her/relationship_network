import Link from "next/link"
import type { ReactNode } from "react"

import { BrandMark } from "@/components/brand-mark"

export function AuthShell({ children }: { readonly children: ReactNode }) {
  return (
    <div className="relative min-h-dvh bg-background">
      <Link
        aria-label="返回 Relationship Network 首页"
        className="absolute top-6 left-6 z-10 rounded-md no-underline outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        href="/"
      >
        <BrandMark />
      </Link>
      <main className="flex min-h-dvh items-center justify-center px-4 py-24">{children}</main>
    </div>
  )
}
