"use client"

import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { MenuIcon, XIcon } from "lucide-react"
import type * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const navbarVariants = cva("group/navbar relative border-b border-border bg-background", {
  variants: {
    sticky: { true: "sticky top-0 z-10", false: "" },
    mobile: { true: "", false: "" },
    menuOpen: { true: "", false: "" },
  },
  defaultVariants: {
    menuOpen: false,
    mobile: false,
    sticky: false,
  },
})

type NavbarProps = React.ComponentProps<"header"> & VariantProps<typeof navbarVariants>

function Navbar({
  className,
  menuOpen = false,
  mobile = false,
  sticky = false,
  ...props
}: NavbarProps) {
  return (
    <header
      className={cn(navbarVariants({ menuOpen, mobile, sticky }), className)}
      data-menu-open={menuOpen}
      data-mobile={mobile}
      data-slot="navbar"
      {...props}
    />
  )
}

function NavbarInner({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "mx-auto flex h-16 w-full max-w-[1400px] items-center gap-6 px-6 max-md:gap-2 max-md:px-4",
        className,
      )}
      data-slot="navbar-inner"
      {...props}
    />
  )
}

function NavbarBrand({ className, render, ...props }: useRender.ComponentProps<"a">) {
  return useRender({
    defaultTagName: "a",
    props: mergeProps<"a">(
      {
        className: cn(
          "inline-flex shrink-0 items-center gap-2 rounded-md text-foreground no-underline outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
        ),
      },
      props,
    ),
    render,
    state: { slot: "navbar-brand" },
  })
}

const mobilePanelClasses =
  "max-md:absolute max-md:inset-x-0 max-md:top-full max-md:hidden max-md:border-b max-md:border-border max-md:bg-background max-md:px-6 max-md:pt-4 max-md:pb-6 group-data-[menu-open=true]/navbar:max-md:block"

function NavbarPrimary({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      aria-label="主导航"
      className={cn(
        mobilePanelClasses,
        "[&_[data-slot=navbar-list]]:max-md:flex-col [&_[data-slot=navbar-list]]:max-md:items-stretch",
        className,
      )}
      data-slot="navbar-primary"
      {...props}
    />
  )
}

function NavbarList({ className, ...props }: React.ComponentProps<"ul">) {
  return (
    <ul
      className={cn("m-0 flex list-none items-center gap-1 p-0", className)}
      data-slot="navbar-list"
      {...props}
    />
  )
}

const navbarItemVariants = cva(
  "inline-flex cursor-pointer items-center gap-2 rounded-md border-0 bg-transparent px-3 py-2 text-sm font-medium leading-normal text-foreground no-underline transition-colors duration-[var(--duration-base)] ease-[var(--ease-standard)] hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-[current=page]:bg-muted aria-[current=page]:font-semibold aria-[current=page]:text-foreground aria-disabled:pointer-events-none aria-disabled:opacity-50 motion-reduce:transition-none max-md:w-full",
  {
    variants: {
      variant: {
        default: "",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

function NavbarItem({
  className,
  render,
  variant = "default",
  ...props
}: useRender.ComponentProps<"a"> & VariantProps<typeof navbarItemVariants>) {
  return useRender({
    defaultTagName: "a",
    props: mergeProps<"a">({ className: cn(navbarItemVariants({ variant }), className) }, props),
    render,
    state: { slot: "navbar-item" },
  })
}

function NavbarActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex items-center gap-2", className)}
      data-slot="navbar-actions"
      {...props}
    />
  )
}

function NavbarDesktopOnly({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("max-md:hidden", className)} data-slot="navbar-desktop-only" {...props} />
  )
}

type NavbarMenuTriggerProps = Omit<React.ComponentProps<typeof Button>, "size"> & {
  menuOpen: boolean
}

function NavbarMenuTrigger({
  "aria-controls": ariaControls,
  className,
  menuOpen,
  ...props
}: NavbarMenuTriggerProps) {
  return (
    <Button
      aria-controls={ariaControls}
      aria-expanded={menuOpen}
      aria-label={menuOpen ? "关闭导航菜单" : "打开导航菜单"}
      className={cn("ms-auto hidden max-md:inline-flex", className)}
      data-slot="navbar-menu-trigger"
      size="icon"
      variant="ghost"
      {...props}
    >
      {menuOpen ? <XIcon /> : <MenuIcon />}
    </Button>
  )
}

export {
  Navbar,
  NavbarActions,
  NavbarBrand,
  NavbarDesktopOnly,
  NavbarInner,
  NavbarItem,
  NavbarList,
  NavbarMenuTrigger,
  NavbarPrimary,
  navbarItemVariants,
}
