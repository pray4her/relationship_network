import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Avatar, AvatarBadge, AvatarFallback } from "@/components/ui/avatar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Navbar,
  NavbarInner,
  NavbarItem,
  NavbarList,
  NavbarMenuTrigger,
  NavbarPrimary,
} from "@/components/ui/navbar"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

describe("new UI navigation and form controls", () => {
  it("renders avatar fallback, size and presence status", () => {
    render(
      <Avatar aria-label="林宁，在线" size="lg">
        <AvatarFallback>林</AvatarFallback>
        <AvatarBadge data-status="online" />
      </Avatar>,
    )

    const avatar = screen.getByLabelText("林宁，在线")
    expect(avatar).toHaveAttribute("data-size", "lg")
    expect(avatar.querySelector('[data-slot="avatar-badge"]')).toHaveAttribute(
      "data-status",
      "online",
    )
  })

  it("preserves checkbox checked and indeterminate semantics", () => {
    const { rerender } = render(<Checkbox aria-label="选择成员" />)
    const checkbox = screen.getByRole("checkbox", { name: "选择成员" })

    fireEvent.click(checkbox)
    expect(checkbox).toBeChecked()

    rerender(<Checkbox aria-label="选择成员" indeterminate />)
    expect(checkbox).toHaveAttribute("data-indeterminate")
  })

  it("keeps radio items mutually exclusive", () => {
    render(
      <RadioGroup aria-label="成员角色" defaultValue="member" name="role">
        <RadioGroupItem aria-label="成员" value="member" />
        <RadioGroupItem aria-label="管理员" value="admin" />
      </RadioGroup>,
    )

    const member = screen.getByRole("radio", { name: "成员" })
    const admin = screen.getByRole("radio", { name: "管理员" })
    expect(member).toBeChecked()
    fireEvent.click(admin)
    expect(admin).toBeChecked()
    expect(member).not.toBeChecked()
  })

  it("renders a semantic breadcrumb with a non-link current page", () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/companies">企业</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>示例企业</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>,
    )

    expect(screen.getByRole("navigation", { name: "面包屑" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "企业" })).toHaveAttribute("href", "/companies")
    expect(screen.getByText("示例企业")).toHaveAttribute("aria-current", "page")
    expect(screen.getByText("示例企业")).toHaveAttribute("aria-disabled", "true")
  })

  it("ties the mobile navigation trigger to the shared navigation panel", () => {
    render(
      <Navbar menuOpen mobile>
        <NavbarInner>
          <NavbarPrimary id="primary-navigation">
            <NavbarList>
              <li>
                <NavbarItem aria-current="page" href="/companies">
                  企业
                </NavbarItem>
              </li>
            </NavbarList>
          </NavbarPrimary>
          <NavbarMenuTrigger aria-controls="primary-navigation" menuOpen />
        </NavbarInner>
      </Navbar>,
    )

    expect(screen.getByRole("link", { name: "企业" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("button", { name: "关闭导航菜单" })).toHaveAttribute(
      "aria-controls",
      "primary-navigation",
    )
  })
})
