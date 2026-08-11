"use client"

import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { MenuIcon, XIcon } from "lucide-react"
import type * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/** 视觉与 markup 规格：frontend/src/styles/navbar.css。 */
const navbarVariants = cva(
  "group/navbar relative border-b-[length:var(--border-width)] border-border-soft bg-background transition-[border-color,box-shadow] duration-normal ease-standard motion-reduce:transition-none",
  {
    variants: {
      sticky: { true: "sticky top-0 z-[var(--z-sticky)]", false: "" },
      scrolled: {
        true: "border-border shadow-subtle",
        false: "",
      },
      mobile: {
        true: "navbar-mobile",
        false: "",
      },
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
        "mx-auto flex h-[var(--space-16)] w-full max-w-[1400px] items-center gap-[var(--space-6)] px-[var(--space-6)] max-md:gap-[var(--space-2)] max-md:px-[var(--space-4)]",
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
          "inline-flex shrink-0 items-center gap-[var(--space-2)] rounded-[var(--radius-md)] text-foreground no-underline focus-visible:outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)]",
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
        "inline-flex size-[var(--brand-mark-size)] shrink-0 items-center justify-center [&_img]:size-full [&_svg]:size-full [&_svg_line]:[stroke-width:var(--stroke-width-brand)]",
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
      className={cn(
        "font-display text-[length:var(--text-title-md)] leading-[var(--text-title-md--line-height)] font-normal",
        className,
      )}
      data-slot="navbar-brand-name"
      {...props}
    />
  )
}

const mobilePanelClasses =
  "max-md:absolute max-md:top-full max-md:inset-x-0 max-md:hidden max-md:border-b-[length:var(--border-width)] max-md:border-border max-md:bg-background max-md:px-[var(--space-6)] max-md:pt-[var(--space-4)] max-md:pb-[var(--space-6)] max-md:shadow-subtle group-data-[menu-open=true]/navbar:max-md:block group-[.navbar-mobile]/navbar:absolute group-[.navbar-mobile]/navbar:top-full group-[.navbar-mobile]/navbar:inset-x-0 group-[.navbar-mobile]/navbar:hidden group-[.navbar-mobile]/navbar:border-b-[length:var(--border-width)] group-[.navbar-mobile]/navbar:border-border group-[.navbar-mobile]/navbar:bg-background group-[.navbar-mobile]/navbar:px-[var(--space-6)] group-[.navbar-mobile]/navbar:pt-[var(--space-4)] group-[.navbar-mobile]/navbar:pb-[var(--space-6)] group-[.navbar-mobile]/navbar:shadow-subtle group-[.navbar-mobile-open]/navbar:block"

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
      className={cn("m-0 flex list-none items-center gap-[var(--space-1)] p-0", className)}
      data-slot="navbar-list"
      {...props}
    />
  )
}

const navbarItemVariants = cva(
  "inline-flex cursor-pointer items-center gap-[var(--space-2)] rounded-[var(--radius-md)] border-0 bg-transparent px-[var(--space-3)] py-[var(--space-2)] font-sans text-[length:var(--text-nav-link)] leading-[var(--text-nav-link--line-height)] font-medium text-foreground no-underline transition-[background-color,color,box-shadow] duration-fast ease-standard hover:bg-accent hover:text-accent-foreground active:bg-surface-cream-strong focus-visible:outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] aria-[current=page]:bg-selected-bg aria-[current=page]:text-foreground aria-[current=page]:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--selected-border)] aria-[current=page]:focus-visible:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--selected-border),0_0_0_var(--ring-width)_var(--ring-focus)] aria-disabled:pointer-events-none aria-disabled:opacity-[var(--opacity-disabled)] data-[state=hover]:bg-accent data-[state=hover]:text-accent-foreground data-[state=active]:bg-surface-cream-strong data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] motion-reduce:transition-none max-md:w-full group-[.navbar-mobile]/navbar:w-full",
  {
    variants: {
      variant: {
        default: "",
        quiet:
          "text-muted-foreground hover:bg-transparent hover:text-muted-foreground-hover active:bg-transparent active:text-muted-foreground-active data-[state=hover]:bg-transparent data-[state=hover]:text-muted-foreground-hover data-[state=active]:bg-transparent data-[state=active]:text-muted-foreground-active",
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
      className={cn(
        "ms-auto w-[calc(var(--space-24)*3)] max-md:hidden group-[.navbar-mobile]/navbar:hidden",
        className,
      )}
      data-slot="navbar-search"
      {...props}
    />
  )
}

function NavbarActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex items-center gap-[var(--space-2)]", className)}
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
        "ms-auto hidden after:absolute after:-inset-[var(--space-1)] aria-expanded:bg-selected-bg max-md:inline-flex group-[.navbar-mobile]/navbar:inline-flex",
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
