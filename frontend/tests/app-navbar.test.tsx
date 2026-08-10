import { fireEvent, render, screen } from "@testing-library/react"
import { usePathname } from "next/navigation"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppNavbar, type AppNavbarAccount } from "@/components/layout/app-navbar"

vi.mock("@/app/actions/auth", () => ({ logoutAction: vi.fn() }))
vi.mock("next/navigation", () => ({ usePathname: vi.fn() }))

const account: AppNavbarAccount = {
  displayName: "张然",
  email: "user@example.com",
  isPlatformAdmin: false,
  permissions: ["companies:read", "jobs:read"],
  role: "member",
  tenantName: "示例租户",
}

describe("AppNavbar", () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReturnValue("/companies")
  })

  it("uses permissions to expose one shared navigation list", () => {
    render(<AppNavbar account={account} />)

    expect(screen.getByRole("link", { name: "平台健康状态" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "企业" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("link", { name: "职位" })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "成员" })).not.toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "平台管理" })).not.toBeInTheDocument()
  })

  it("toggles the mobile panel through aria-expanded", () => {
    render(<AppNavbar account={account} />)
    const trigger = screen.getByRole("button", { name: "打开导航菜单" })

    fireEvent.click(trigger)
    expect(screen.getByRole("button", { name: "关闭导航菜单" })).toHaveAttribute(
      "aria-expanded",
      "true",
    )
  })

  it("keeps a visible platform administration context", () => {
    vi.mocked(usePathname).mockReturnValue("/admin/orders")
    render(<AppNavbar account={{ ...account, isPlatformAdmin: true }} />)

    expect(screen.getByText("平台管理模式")).toBeInTheDocument()
    expect(screen.getByText("此区域可跨租户读取，请确认操作对象。")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "平台管理" })).toHaveAttribute("aria-current", "page")
  })

  it("shows only public navigation and account entry points for visitors", () => {
    vi.mocked(usePathname).mockReturnValue("/")
    render(<AppNavbar account={null} />)

    expect(screen.getByRole("link", { name: "平台健康状态" })).toHaveAttribute(
      "aria-current",
      "page",
    )
    expect(screen.queryByRole("link", { name: "企业" })).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "登录" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "注册" })).toBeInTheDocument()
  })
})
