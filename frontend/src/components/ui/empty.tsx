import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/empty-state.css(showcase/empty-state.html 为唯一标准)。
 * 空置区域的内容驱动占位组件:自身无交互,规格明确不定义 focus/disabled/transition
 * —— 这些状态全部来自组合的 Button / Link(预览页 actions 章节经 data-state 静态渲染)。
 *
 * API 映射(原 shadcn 风格 API → 规格 markup 合同):
 * - Empty            → .empty-state;规格的四个语义场景收为 variant
 *                      (first-use / no-results / no-data / error,默认 no-data 中性场景),
 *                      经 data-variant 下发色调(对应规格 alert.css 式私有属性
 *                      --_chip-bg / --_icon,chip 与插槽用 group-data 镜像读取)
 * - EmptyHeader      → 规格无独立 header 节点;渲染为 display:contents 的语义分组,
 *                      让 title/description 直接参与根节点的 --space-3 节奏
 * - EmptyMedia       → variant="icon" = .empty-state__icon 圆形 chip(规格默认处理,
 *                      --avatar-size-xl 容器 + --icon-size-lg 字形);
 *                      variant="default" = .empty-state__illustration 内容驱动插槽
 *                      (不设尺寸,仅经 currentColor 透传 variant 色调)
 * - EmptyTitle       → .empty-state__title(规格为 heading 元素,此处保持 div,
 *                      语义层级由调用方经外层结构决定)
 * - EmptyDescription → .empty-state__description(度量上限由根节点 max-width 承担)
 * - EmptyContent     → .empty-state__actions:flex 行,子项是未改样式的 Button/Link;
 *                      无动作时整个节点省略
 */

/** 规格的四个语义场景;色调经 data-variant + group-data 下发给 media 子节点。 */
type EmptyVariant = "first-use" | "no-results" | "no-data" | "error"

function Empty({
  className,
  variant = "no-data",
  ...props
}: React.ComponentProps<"div"> & { variant?: EmptyVariant }) {
  return (
    <div
      className={cn(
        "group/empty mx-auto grid max-w-[calc(var(--space-24)*5)] justify-items-center gap-[var(--space-3)] px-[var(--space-6)] py-[var(--space-12)] text-center max-md:py-[var(--space-8)]",
        className,
      )}
      data-slot="empty"
      data-variant={variant}
      {...props}
    />
  )
}

function EmptyHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("contents", className)} data-slot="empty-header" {...props} />
}

const emptyMediaVariants = cva("shrink-0 [&_svg]:pointer-events-none", {
  variants: {
    variant: {
      // .empty-state__illustration:内容驱动,资产自带尺寸,插槽只透传 variant 色调
      default:
        "block text-muted-foreground group-data-[variant=first-use]/empty:text-info group-data-[variant=error]/empty:text-destructive",
      // .empty-state__icon:圆形 chip;基色为 no-data(默认 variant),其余场景经 group-data 覆盖
      icon: "inline-flex size-[var(--avatar-size-xl)] items-center justify-center rounded-[var(--radius-full)] bg-card text-muted-foreground group-data-[variant=first-use]/empty:bg-info-soft group-data-[variant=first-use]/empty:text-info group-data-[variant=no-results]/empty:bg-surface-soft group-data-[variant=error]/empty:bg-destructive-soft group-data-[variant=error]/empty:text-destructive [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-lg)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
    },
  },
  defaultVariants: {
    variant: "icon",
  },
})

function EmptyMedia({
  className,
  variant = "icon",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof emptyMediaVariants>) {
  return (
    <div
      data-slot="empty-icon"
      data-variant={variant}
      className={cn(emptyMediaVariants({ variant, className }))}
      {...props}
    />
  )
}

function EmptyTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "font-sans text-[length:var(--text-title-lg)] leading-[var(--text-title-lg--line-height)] font-medium text-foreground",
        className,
      )}
      data-slot="empty-title"
      {...props}
    />
  )
}

function EmptyDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <div
      className={cn(
        "font-sans text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)] text-muted-foreground",
        className,
      )}
      data-slot="empty-description"
      {...props}
    />
  )
}

function EmptyContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "mt-[var(--space-3)] flex flex-wrap items-center justify-center gap-[var(--space-3)]",
        className,
      )}
      data-slot="empty-content"
      {...props}
    />
  )
}

export { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle }
