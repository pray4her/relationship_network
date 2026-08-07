"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"

const links = [
  { href: "/", label: "首页" },
  { href: "/members", label: "成员", permission: "members:read" },
  { href: "/companies", label: "企业", permission: "companies:read" },
  { href: "/jobs", label: "职位", permission: "jobs:read" },
  { href: "/usage", label: "用量与套餐", permission: "billing:read" },
  { href: "/settings/security", label: "安全设置" },
  { href: "/admin", label: "平台管理", admin: true },
] as const

type WorkspaceNavProps = {
  readonly permissions: readonly string[]
  readonly isPlatformAdmin: boolean
}

export function WorkspaceNav({ isPlatformAdmin, permissions }: WorkspaceNavProps) {
  const pathname = usePathname()

  return (
    <nav aria-label="工作区" className="flex flex-wrap gap-1">
      {links.map((link) => {
        if (
          "permission" in link &&
          link.permission !== undefined &&
          !permissions.includes(link.permission)
        ) {
          return null
        }
        if ("admin" in link && link.admin && !isPlatformAdmin) {
          return null
        }
        const isActive = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href)
        return (
          <Link
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors duration-200 hover:bg-muted hover:text-foreground",
              isActive && "bg-muted text-accent",
            )}
            href={link.href}
            key={link.href}
          >
            {link.label}
          </Link>
        )
      })}
    </nav>
  )
}
