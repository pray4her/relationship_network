"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"

import { logoutAction } from "@/app/actions/auth"
import { BrandMark } from "@/components/brand-mark"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Navbar,
  NavbarActions,
  NavbarBrand,
  NavbarDesktopOnly,
  NavbarInner,
  NavbarItem,
  NavbarList,
  NavbarMenuTrigger,
  NavbarPrimary,
} from "@/components/ui/navbar"

const navigationItems = [
  { href: "/", label: "平台健康状态" },
  { href: "/members", label: "成员", permission: "members:read" },
  { href: "/companies", label: "企业", permission: "companies:read" },
  { href: "/jobs", label: "职位", permission: "jobs:read" },
  { href: "/usage", label: "用量与套餐", permission: "billing:read" },
  { href: "/settings/security", label: "安全设置" },
  { admin: true, href: "/admin", label: "平台管理" },
] as const

export type AppNavbarAccount = {
  readonly displayName: string
  readonly email: string
  readonly isPlatformAdmin: boolean
  readonly permissions: readonly string[]
  readonly role: "member" | "owner" | null
  readonly tenantName: string | null
}

function isCurrentPath(pathname: string, href: string): boolean {
  return href === "/" ? pathname === href : pathname.startsWith(href)
}

function initialFor(displayName: string): string {
  return displayName.trim().slice(0, 1).toUpperCase() || "账"
}

export function AppNavbar({ account }: { readonly account: AppNavbarAccount | null }) {
  const pathname = usePathname()
  const [menuOpen, setMenuOpen] = useState(false)
  const adminMode = account?.isPlatformAdmin === true && pathname.startsWith("/admin")
  const availableItems = navigationItems.filter((item) => {
    if (
      "permission" in item &&
      item.permission &&
      !account?.permissions.includes(item.permission)
    ) {
      return false
    }
    if ("admin" in item && item.admin && !account?.isPlatformAdmin) {
      return false
    }
    return item.href === "/" || account !== null
  })

  return (
    <Navbar menuOpen={menuOpen} sticky>
      <NavbarInner>
        <NavbarBrand
          render={
            <Link href="/">
              <BrandMark />
            </Link>
          }
        />
        <NavbarPrimary id="primary-navigation">
          <NavbarList>
            {availableItems.map((item) => (
              <li key={item.href}>
                <NavbarItem
                  aria-current={isCurrentPath(pathname, item.href) ? "page" : undefined}
                  render={
                    <Link href={item.href} onClick={() => setMenuOpen(false)}>
                      {item.label}
                    </Link>
                  }
                />
              </li>
            ))}
          </NavbarList>
        </NavbarPrimary>

        <NavbarActions className="ms-auto">
          {account === null ? (
            <>
              <NavbarDesktopOnly>
                <Link className={buttonVariants({ size: "sm", variant: "ghost" })} href="/login">
                  登录
                </Link>
              </NavbarDesktopOnly>
              <NavbarDesktopOnly>
                <Link className={buttonVariants({ size: "sm" })} href="/register">
                  注册
                </Link>
              </NavbarDesktopOnly>
            </>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button aria-label="打开账户菜单" size="sm" variant="ghost">
                    <Avatar aria-hidden="true" size="sm">
                      <AvatarFallback>{initialFor(account.displayName)}</AvatarFallback>
                    </Avatar>
                    <span className="max-w-32 truncate max-md:sr-only">{account.displayName}</span>
                  </Button>
                }
              />
              <DropdownMenuContent align="end">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>{account.displayName}</DropdownMenuLabel>
                  <DropdownMenuItem disabled>{account.email}</DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuLabel>租户</DropdownMenuLabel>
                  <DropdownMenuItem disabled>
                    {account.tenantName ??
                      (account.isPlatformAdmin ? "平台管理员，无租户" : "无租户")}
                  </DropdownMenuItem>
                  {account.role ? (
                    <DropdownMenuItem disabled>
                      {account.role === "owner" ? "租户所有者" : "成员"}
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem render={<Link href="/settings/security">安全设置</Link>} />
                  <form action={logoutAction}>
                    <DropdownMenuItem render={<button type="submit">退出登录</button>} />
                  </form>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </NavbarActions>
        <NavbarMenuTrigger
          aria-controls="primary-navigation"
          menuOpen={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        />
      </NavbarInner>
      {adminMode ? (
        <div className="border-t border-warning bg-warning/10">
          <div className="mx-auto flex min-h-8 w-full max-w-[1400px] items-center gap-3 px-6 py-1">
            <Badge variant="outline">平台管理模式</Badge>
            <span className="text-xs leading-normal text-muted-foreground">
              此区域可跨租户读取，请确认操作对象。
            </span>
          </div>
        </div>
      ) : null}
    </Navbar>
  )
}
