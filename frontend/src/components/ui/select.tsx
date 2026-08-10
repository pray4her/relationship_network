"use client"

import { Select as SelectPrimitive } from "@base-ui/react/select"
import { cva, type VariantProps } from "class-variance-authority"
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react"
import type * as React from "react"
import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/select.css(showcase/select.html 为唯一标准)。
 * trigger 与 Input 家族共享 field chrome;hover/focus-visible 同时挂伪类与
 * data-[state=*] 镜像,预览页可静态渲染;open 态经 aria-expanded 呈现聚焦环
 * 与 chevron 半周旋转(--motion-rotation-full / 2)。
 *
 * API 映射说明(规格 → 现有 API):
 * - size:规格 sm/md/lg;现有 API 的 "default" 映射到 md,--control-height;
 *   "sm" 映射到 --control-height-sm;新增可选 "lg" 映射到 --control-height-lg。
 * - 规格无 loading 状态,不新增 loading prop。
 * - 规格的 --menu-max-height(六行)经 max-h 落在 Popup;sideOffset 默认值 4px
 *   即 --space-1(trigger ↔ menu 间距)。
 * - 规格 .select--sm 的 option 字号联动依赖根级 class,而 Popup 走 portal,
 *   无法继承;option 固定 body-md 字号,视为规格缺口(见汇报)。
 */

const Select = SelectPrimitive.Root

const selectTriggerVariants = cva(
  "group/select-trigger flex w-full cursor-pointer items-center gap-[var(--space-2)] rounded-[var(--radius-md)] border-[length:var(--border-width)] border-input bg-background px-[var(--input-padding-inline)] text-left font-sans text-base text-foreground outline-none select-none transition-[border-color,box-shadow] duration-fast ease-standard not-disabled:hover:border-border-strong focus-visible:border-primary focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] aria-expanded:border-primary aria-expanded:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] aria-invalid:border-destructive aria-invalid:focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] aria-invalid:aria-expanded:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=hover]:border-border-strong data-[state=focus-visible]:border-primary data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] aria-invalid:data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] data-placeholder:[&_[data-slot=select-value]]:text-caption-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
  {
    variants: {
      size: {
        // 规格 .select--sm:--control-height-sm + --text-body-sm
        sm: "h-[var(--control-height-sm)] text-sm",
        // 规格默认(md):--control-height + --text-body-md(= text-base)
        default: "h-[var(--control-height)]",
        // 规格 .select--lg:--control-height-lg
        lg: "h-[var(--control-height-lg)]",
      },
    },
    defaultVariants: {
      size: "default",
    },
  },
)

function SelectGroup({ className, ...props }: SelectPrimitive.Group.Props) {
  return (
    <SelectPrimitive.Group
      data-slot="select-group"
      className={cn(
        "scroll-my-[var(--space-1)] p-0 [[data-slot=select-group]+&]:mt-[var(--space-1)] [[data-slot=select-group]+&]:border-t-[length:var(--border-width)] [[data-slot=select-group]+&]:border-border-soft [[data-slot=select-group]+&]:pt-[var(--space-1)]",
        className,
      )}
      {...props}
    />
  )
}

function SelectValue({ className, ...props }: SelectPrimitive.Value.Props) {
  return (
    <SelectPrimitive.Value
      data-slot="select-value"
      className={cn("min-w-0 flex-1 truncate text-left", className)}
      {...props}
    />
  )
}

function SelectTrigger({
  className,
  size = "default",
  children,
  ...props
}: SelectPrimitive.Trigger.Props & VariantProps<typeof selectTriggerVariants>) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      data-size={size}
      className={cn(selectTriggerVariants({ size }), className)}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon
        render={
          <ChevronDownIcon className="text-caption-foreground transition-[rotate] duration-fast ease-standard group-aria-expanded/select-trigger:[rotate:calc(var(--motion-rotation-full)/2)]" />
        }
      />
    </SelectPrimitive.Trigger>
  )
}

function SelectContent({
  className,
  children,
  side = "bottom",
  sideOffset = 4,
  align = "center",
  alignOffset = 0,
  alignItemWithTrigger = true,
  collisionAvoidance,
  ...props
}: SelectPrimitive.Popup.Props &
  Pick<
    SelectPrimitive.Positioner.Props,
    "align" | "alignOffset" | "side" | "sideOffset" | "alignItemWithTrigger" | "collisionAvoidance"
  >) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
        alignItemWithTrigger={alignItemWithTrigger}
        collisionAvoidance={collisionAvoidance}
        className="isolate z-[var(--z-dropdown)]"
      >
        <SelectPrimitive.Popup
          data-slot="select-content"
          data-align-trigger={alignItemWithTrigger}
          className={cn(
            "relative isolate max-h-[var(--menu-max-height)] w-(--anchor-width) overflow-x-hidden overflow-y-auto overscroll-contain rounded-[var(--radius-md)] border-[length:var(--border-width)] border-border bg-popover p-[var(--space-1)] font-sans text-popover-foreground shadow-subtle",
            className,
          )}
          {...props}
        >
          <SelectScrollUpButton />
          <SelectPrimitive.List>{children}</SelectPrimitive.List>
          <SelectScrollDownButton />
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  )
}

function SelectLabel({ className, ...props }: SelectPrimitive.GroupLabel.Props) {
  return (
    <SelectPrimitive.GroupLabel
      data-slot="select-label"
      className={cn(
        "px-[var(--space-3)] py-[var(--space-2)] font-sans text-xs font-medium uppercase tracking-[var(--text-caption-up--letter-spacing)] text-muted-foreground",
        className,
      )}
      {...props}
    />
  )
}

function SelectItem({ className, children, ...props }: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "flex w-full cursor-pointer items-center gap-[var(--space-2)] rounded-[var(--radius-xs)] px-[var(--space-3)] py-[var(--space-2)] font-sans text-base text-foreground outline-none select-none transition-[background-color,color] duration-fast ease-standard hover:bg-accent data-highlighted:bg-accent data-selected:bg-surface-cream-strong data-selected:hover:bg-accent data-selected:data-highlighted:bg-accent data-disabled:cursor-not-allowed data-disabled:opacity-[var(--opacity-disabled)] data-disabled:hover:bg-transparent data-disabled:data-highlighted:bg-transparent data-[state=hover]:bg-accent data-selected:data-[state=hover]:bg-accent data-disabled:data-[state=hover]:bg-transparent [&_[data-slot=select-item-indicator]]:invisible data-selected:[&_[data-slot=select-item-indicator]]:visible [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText className="min-w-0 flex-1 truncate">
        {children}
      </SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator
        keepMounted
        data-slot="select-item-indicator"
        className="ml-auto flex-none text-primary"
        render={<span />}
      >
        <CheckIcon />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  )
}

function SelectSeparator({ className, ...props }: SelectPrimitive.Separator.Props) {
  return (
    <SelectPrimitive.Separator
      data-slot="select-separator"
      className={cn(
        "pointer-events-none -mx-[var(--space-1)] my-[var(--space-1)] h-[var(--border-width)] bg-border-soft",
        className,
      )}
      {...props}
    />
  )
}

function SelectScrollUpButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollUpArrow>) {
  return (
    <SelectPrimitive.ScrollUpArrow
      data-slot="select-scroll-up-button"
      className={cn(
        "top-0 z-10 flex w-full cursor-default items-center justify-center bg-popover py-[var(--space-1)] [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
        className,
      )}
      {...props}
    >
      <ChevronUpIcon />
    </SelectPrimitive.ScrollUpArrow>
  )
}

function SelectScrollDownButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollDownArrow>) {
  return (
    <SelectPrimitive.ScrollDownArrow
      data-slot="select-scroll-down-button"
      className={cn(
        "bottom-0 z-10 flex w-full cursor-default items-center justify-center bg-popover py-[var(--space-1)] [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
        className,
      )}
      {...props}
    >
      <ChevronDownIcon />
    </SelectPrimitive.ScrollDownArrow>
  )
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
}
