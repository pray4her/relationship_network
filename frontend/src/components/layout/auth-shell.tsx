import Link from "next/link"
import type { ReactNode } from "react"

import { BrandMark } from "@/components/brand-mark"

export function AuthShell({ children }: { readonly children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-background">
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:underline"
        href="#main-content"
      >
        跳到主内容
      </a>
      <main
        className="mx-auto flex min-h-dvh w-full max-w-lg flex-col justify-center gap-8 px-4 py-10"
        id="main-content"
      >
        <Link
          aria-label="返回 Relationship Network 首页"
          className="self-center rounded-md no-underline outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          href="/"
        >
          <BrandMark />
        </Link>
        {children}
      </main>
    </div>
  )
}
