"use client"

import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { MenuIcon, XIcon } from "lucide-react"
import type * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const navbarVariants = cva(
  "group/navbar relative border-b border-border bg-background transition-[border-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-standard)] motion-reduce:transition-none",
  {
    variants: {
      sticky: { true: "sticky top-0 z-10", false: "" },
      scrolled: { true: "border-border", false: "" },
      mobile: { true: "navbar-mobile", false: "" },
      menuOpen: { true: "", false: "" },
    },
    compoundVariants: [{ mobile: true, menuOpen: true, className: "navbar-mobile-open" }],
    defaultVariants: {
      menuOpen: false,
      mobile: false,
      scrolled: false,
      sticky: false,
    },
  },
)

type NavbarProps = React.ComponentProps<"header"> & VariantProps<typeof navbarVariants>

function Navbar({
  className,
  menuOpen = false,
  mobile = false,
  scrolled = false,
  sticky = false,
  ...props
}: NavbarProps) {
  return (
    <header
      className={cn(navbarVariants({ menuOpen, mobile, scrolled, sticky }), className)}
      data-menu-open={menuOpen}
      data-mobile={mobile}
      data-scrolled={scrolled}
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

function NavbarBrandMark({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-5 shrink-0 items-center justify-center [&_img]:size-full [&_svg]:size-full",
        className,
      )}
      data-slot="navbar-brand-mark"
      {...props}
    />
  )
}

function NavbarBrandName({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      className={cn("text-base font-semibold leading-normal text-foreground", className)}
      data-slot="navbar-brand-name"
      {...props}
    />
  )
}

const mobilePanelClasses =
  "max-md:absolute max-md:inset-x-0 max-md:top-full max-md:hidden max-md:border-b max-md:border-border max-md:bg-background max-md:px-6 max-md:pt-4 max-md:pb-6 group-data-[menu-open=true]/navbar:max-md:block group-[.navbar-mobile]/navbar:absolute group-[.navbar-mobile]/navbar:inset-x-0 group-[.navbar-mobile]/navbar:top-full group-[.navbar-mobile]/navbar:hidden group-[.navbar-mobile]/navbar:border-b group-[.navbar-mobile]/navbar:border-border group-[.navbar-mobile]/navbar:bg-background group-[.navbar-mobile]/navbar:px-6 group-[.navbar-mobile]/navbar:pt-4 group-[.navbar-mobile]/navbar:pb-6 group-[.navbar-mobile-open]/navbar:block"

function NavbarPrimary({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      aria-label="主导航"
      className={cn(
        mobilePanelClasses,
        "[&_[data-slot=navbar-list]]:max-md:flex-col [&_[data-slot=navbar-list]]:max-md:items-stretch group-[.navbar-mobile]/navbar:[&_[data-slot=navbar-list]]:flex-col group-[.navbar-mobile]/navbar:[&_[data-slot=navbar-list]]:items-stretch",
        className,
      )}
      data-slot="navbar-primary"
      {...props}
    />
  )
}

function NavbarSecondary({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      aria-label="辅助导航"
      className={cn("max-md:hidden group-[.navbar-mobile]/navbar:hidden", className)}
      data-slot="navbar-secondary"
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
  "inline-flex cursor-pointer items-center gap-2 rounded-md border-0 bg-transparent px-3 py-2 text-sm font-medium leading-normal text-foreground no-underline transition-colors duration-[var(--duration-base)] ease-[var(--ease-standard)] hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-[current=page]:bg-muted aria-[current=page]:text-muted-foreground aria-disabled:pointer-events-none aria-disabled:opacity-50 motion-reduce:transition-none max-md:w-full group-[.navbar-mobile]/navbar:w-full",
  {
    variants: {
      variant: {
        default: "",
        quiet: "text-foreground hover:bg-transparent hover:text-muted-foreground",
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

function NavbarSearch({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("ms-auto w-72 max-md:hidden group-[.navbar-mobile]/navbar:hidden", className)}
      data-slot="navbar-search"
      {...props}
    />
  )
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
    <div
      className={cn("max-md:hidden group-[.navbar-mobile]/navbar:hidden", className)}
      data-slot="navbar-desktop-only"
      {...props}
    />
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
      className={cn(
        "ms-auto hidden max-md:inline-flex group-[.navbar-mobile]/navbar:inline-flex",
        className,
      )}
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
  NavbarBrandMark,
  NavbarBrandName,
  NavbarDesktopOnly,
  NavbarInner,
  NavbarItem,
  NavbarList,
  NavbarMenuTrigger,
  NavbarPrimary,
  NavbarSearch,
  NavbarSecondary,
  navbarItemVariants,
  navbarVariants,
}
