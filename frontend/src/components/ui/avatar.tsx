"use client"

import { Avatar as AvatarPrimitive } from "@base-ui/react/avatar"
import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

/** 视觉规格：frontend/src/styles/avatar.css。 */
const avatarVariants = cva(
  "group/avatar relative inline-flex shrink-0 items-center justify-center rounded-[var(--radius-full)] p-0 font-sans font-medium text-foreground no-underline select-none [&_svg]:shrink-0 [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
  {
    variants: {
      size: {
        xs: "size-[var(--avatar-size-xs)] text-[length:var(--text-caption-up)] leading-[var(--text-caption-up--line-height)] tracking-[var(--text-caption-up--letter-spacing)] uppercase",
        sm: "size-[var(--avatar-size-sm)] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)]",
        default:
          "size-[var(--avatar-size-md)] text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)]",
        lg: "size-[var(--avatar-size-lg)] text-[length:var(--text-title-sm)] leading-[var(--text-title-sm--line-height)]",
        xl: "size-[var(--avatar-size-xl)] text-[length:var(--text-title-md)] leading-[var(--text-title-md--line-height)]",
      },
      variant: {
        image: "bg-transparent",
        initials: "border-[length:var(--border-width)] border-border bg-card text-foreground",
        generic: "border-[length:var(--border-width)] border-border bg-muted text-muted-foreground",
      },
      interactive: {
        true: "cursor-pointer transition-shadow duration-fast ease-standard hover:shadow-subtle active:shadow-[inset_0_0_0_var(--border-width-strong)_var(--selected-border)] focus-visible:outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=hover]:shadow-subtle data-[state=active]:shadow-[inset_0_0_0_var(--border-width-strong)_var(--selected-border)] data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-disabled:cursor-not-allowed data-disabled:opacity-[var(--opacity-disabled)] motion-reduce:transition-none",
        false: "",
      },
    },
    defaultVariants: {
      interactive: false,
      size: "default",
      variant: "image",
    },
  },
)

type AvatarProps = AvatarPrimitive.Root.Props &
  VariantProps<typeof avatarVariants> & {
    /** 当 Root 通过 render 变为链接或按钮时启用完整交互态。 */
    interactive?: boolean
  }

function Avatar({
  className,
  interactive = false,
  size = "default",
  variant = "image",
  ...props
}: AvatarProps) {
  return (
    <AvatarPrimitive.Root
      className={cn(avatarVariants({ interactive, size, variant }), className)}
      data-interactive={interactive || undefined}
      data-size={size}
      data-slot="avatar"
      data-variant={variant}
      {...props}
    />
  )
}

function AvatarImage({ className, ...props }: AvatarPrimitive.Image.Props) {
  return (
    <AvatarPrimitive.Image
      className={cn("block size-full rounded-[var(--radius-full)] object-cover", className)}
      data-slot="avatar-image"
      {...props}
    />
  )
}

function AvatarFallback({ className, ...props }: AvatarPrimitive.Fallback.Props) {
  return (
    <AvatarPrimitive.Fallback
      className={cn(
        "flex size-full items-center justify-center rounded-[var(--radius-full)] border-[length:var(--border-width)] border-border bg-card text-current group-data-[size=xs]/avatar:ps-[var(--text-caption-up--letter-spacing)] group-data-[variant=generic]/avatar:bg-muted group-data-[variant=generic]/avatar:text-muted-foreground",
        className,
      )}
      data-slot="avatar-fallback"
      {...props}
    />
  )
}

const avatarStatusVariants = cva(
  "absolute end-0 bottom-0 inline-flex size-[var(--space-2)] items-center justify-center rounded-[var(--radius-full)] shadow-[0_0_0_var(--border-width)_var(--background)] group-data-[size=lg]/avatar:size-[var(--space-3)] group-data-[size=xl]/avatar:size-[var(--space-3)]",
  {
    variants: {
      status: {
        online: "bg-[var(--status-online)]",
        offline: "bg-[var(--status-offline)]",
        busy: "bg-[var(--status-busy)]",
        away: "bg-[var(--status-away)]",
      },
    },
    defaultVariants: { status: "offline" },
  },
)

function AvatarBadge({
  className,
  status = "offline",
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof avatarStatusVariants>) {
  return (
    <span
      aria-hidden="true"
      className={cn(avatarStatusVariants({ status }), className)}
      data-slot="avatar-badge"
      data-status={status}
      {...props}
    />
  )
}

/** 规格未定义堆叠组；沿用 shadcn API，并映射到现有间距与背景 token。 */
function AvatarGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "group/avatar-group flex -space-x-[var(--space-2)] *:data-[slot=avatar]:ring-2 *:data-[slot=avatar]:ring-background",
        className,
      )}
      data-slot="avatar-group"
      {...props}
    />
  )
}

function AvatarGroupCount({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "relative flex size-[var(--avatar-size-md)] shrink-0 items-center justify-center rounded-[var(--radius-full)] bg-muted font-sans text-[length:var(--text-body-sm)] text-muted-foreground ring-2 ring-background group-has-data-[size=lg]/avatar-group:size-[var(--avatar-size-lg)] group-has-data-[size=sm]/avatar-group:size-[var(--avatar-size-sm)]",
        className,
      )}
      data-slot="avatar-group-count"
      {...props}
    />
  )
}

export {
  Avatar,
  AvatarBadge,
  AvatarFallback,
  AvatarGroup,
  AvatarGroupCount,
  AvatarImage,
  avatarVariants,
}
