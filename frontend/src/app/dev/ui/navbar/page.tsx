"use client"

import { NetworkIcon } from "lucide-react"
import { useState } from "react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Navbar,
  NavbarActions,
  NavbarBrand,
  NavbarBrandMark,
  NavbarBrandName,
  NavbarDesktopOnly,
  NavbarInner,
  NavbarItem,
  NavbarList,
  NavbarMenuTrigger,
  NavbarPrimary,
} from "@/components/ui/navbar"

import { PreviewPage, PreviewSection } from "../_preview"

const items = [
  { href: "#health", label: "平台健康状态" },
  { href: "#members", label: "成员" },
  { href: "#companies", label: "企业" },
  { href: "#jobs", label: "职位" },
]

function PreviewNavigation() {
  return (
    <NavbarList>
      {items.map((item) => (
        <li key={item.href}>
          <NavbarItem
            aria-current={item.href === "#companies" ? "page" : undefined}
            href={item.href}
          >
            {item.label}
          </NavbarItem>
        </li>
      ))}
    </NavbarList>
  )
}

export default function NavbarPreviewPage() {
  const [menuOpen, setMenuOpen] = useState(true)
  const [responsiveMenuOpen, setResponsiveMenuOpen] = useState(false)

  return (
    <PreviewPage
      description="桌面与移动端共享同一导航列表；当前项只由 aria-current 表达，菜单按钮同步 aria-expanded。"
      title="Navbar"
    >
      <PreviewSection title="桌面">
        <Navbar menuOpen={responsiveMenuOpen} scrolled>
          <NavbarInner>
            <NavbarBrand href="#brand">
              <NavbarBrandMark>
                <NetworkIcon />
              </NavbarBrandMark>
              <NavbarBrandName>Relationship Network</NavbarBrandName>
            </NavbarBrand>
            <NavbarPrimary id="preview-responsive-navigation">
              <PreviewNavigation />
            </NavbarPrimary>
            <NavbarActions className="ms-auto">
              <NavbarDesktopOnly>
                <Button size="sm">新建企业</Button>
              </NavbarDesktopOnly>
              <Avatar aria-label="账户" size="sm" variant="initials">
                <AvatarFallback>张</AvatarFallback>
              </Avatar>
            </NavbarActions>
            <NavbarMenuTrigger
              aria-controls="preview-responsive-navigation"
              menuOpen={responsiveMenuOpen}
              onClick={() => setResponsiveMenuOpen((open) => !open)}
            />
          </NavbarInner>
        </Navbar>
      </PreviewSection>

      <PreviewSection title="移动菜单">
        <Navbar menuOpen={menuOpen} mobile>
          <NavbarInner>
            <NavbarBrand href="#mobile-brand">
              <NavbarBrandMark>
                <NetworkIcon />
              </NavbarBrandMark>
              <NavbarBrandName>Relationship Network</NavbarBrandName>
            </NavbarBrand>
            <NavbarPrimary id="preview-mobile-navigation">
              <PreviewNavigation />
            </NavbarPrimary>
            <NavbarMenuTrigger
              aria-controls="preview-mobile-navigation"
              menuOpen={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            />
          </NavbarInner>
        </Navbar>
      </PreviewSection>
    </PreviewPage>
  )
}
