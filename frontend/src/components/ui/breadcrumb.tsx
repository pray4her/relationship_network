import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { ChevronRightIcon, MoreHorizontalIcon } from "lucide-react"
import type * as React from "react"

import { cn } from "@/lib/utils"

/** 视觉与 markup 规格：frontend/src/styles/breadcrumb.css。 */
function Breadcrumb({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      aria-label="面包屑"
      className={cn("min-w-0", className)}
      data-slot="breadcrumb"
      {...props}
    />
  )
}

function BreadcrumbList({ className, ...props }: React.ComponentProps<"ol">) {
  return (
    <ol
      className={cn(
        "m-0 inline-flex list-none flex-wrap items-center gap-[var(--space-2)] p-0 font-sans text-[length:var(--text-nav-link)] leading-[var(--text-nav-link--line-height)] font-medium",
        className,
      )}
      data-slot="breadcrumb-list"
      {...props}
    />
  )
}

function BreadcrumbItem({ className, ...props }: React.ComponentProps<"li">) {
  return (
    <li
      className={cn("inline-flex min-w-0 items-center", className)}
      data-slot="breadcrumb-item"
      {...props}
    />
  )
}

function BreadcrumbLink({ className, render, ...props }: useRender.ComponentProps<"a">) {
  return useRender({
    defaultTagName: "a",
    props: mergeProps<"a">(
      {
        className: cn(
          "inline-flex min-w-0 items-center gap-[var(--space-1)] truncate rounded-[var(--radius-xs)] text-muted-foreground no-underline transition-[color,box-shadow] duration-fast ease-standard hover:text-muted-foreground-hover focus-visible:outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=hover]:text-muted-foreground-hover data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] motion-reduce:transition-none",
          className,
        ),
      },
      props,
    ),
    render,
    state: { slot: "breadcrumb-link" },
  })
}

function BreadcrumbPage({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-current="page"
      className={cn(
        "inline-flex min-w-0 items-center gap-[var(--space-1)] truncate rounded-[var(--radius-sm)] bg-selected-bg px-[var(--space-2)] py-[var(--space-0-5)] text-foreground shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--selected-border)]",
        className,
      )}
      data-slot="breadcrumb-page"
      {...props}
    />
  )
}

function BreadcrumbSeparator({ children, className, ...props }: React.ComponentProps<"li">) {
  return (
    <li
      aria-hidden="true"
      className={cn(
        "inline-flex shrink-0 list-none items-center text-muted-foreground [&_svg]:size-[var(--icon-size-xs)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
        className,
      )}
      data-slot="breadcrumb-separator"
      role="presentation"
      {...props}
    >
      {children ?? <ChevronRightIcon />}
    </li>
  )
}

function BreadcrumbEllipsis({
  className,
  type = "button",
  ...props
}: React.ComponentProps<"button">) {
  return (
    <button
      aria-haspopup="menu"
      aria-label="显示隐藏的路径"
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--radius-sm)] border-[length:var(--border-width)] border-transparent bg-transparent p-[var(--space-1)] text-muted-foreground transition-[color,background-color,box-shadow] duration-fast ease-standard hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] aria-expanded:bg-selected-bg aria-expanded:text-foreground data-[state=hover]:bg-accent data-[state=hover]:text-accent-foreground data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=expanded]:bg-selected-bg data-[state=expanded]:text-foreground motion-reduce:transition-none [&_svg]:size-[var(--icon-size-sm)]",
        className,
      )}
      data-slot="breadcrumb-ellipsis"
      type={type}
      {...props}
    >
      <MoreHorizontalIcon />
    </button>
  )
}

export {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
}
