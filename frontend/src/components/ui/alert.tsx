import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/alert.css(showcase 为唯一标准)。
 * 解剖合同:icon(前导 svg)+ body(title / description / actions)+ dismiss。
 * 网格列:恒为 auto 1fr auto —— icon / dismiss 缺省时对应 auto 列塌缩为 0,
 * body 元素经 group-has 落到正确的列(与规格同一模板、自动 placement 等价)。
 *
 * API 映射(规格无同名物时取最近规格,见 showcase/alert.html):
 * - variant "default" → 规格 neutral(card/border/foreground/muted 无状态色)
 * - variant "info" | "success" | "warning" → 规格同名变体(新增)
 * - variant "destructive" → 规格同名变体
 * - AlertAction → 规格 .alert__actions(body 内动作簇,组合真实 Button/Link,
 *   不再做旧版的 absolute 右上角定位——右上角那是 dismiss 槽位)
 * - AlertDismiss(新增,可选)→ 规格 .alert__dismiss;状态同时挂伪类与
 *   data-[state=hover|active|focus-visible] 镜像,预览页可静态渲染。
 *
 * 规格明确不强制 live-region role(急迫度由调用方选 role="alert"/"status"/
 * 无),因此根节点不再默认 role="alert"。
 */
const alertVariants = cva(
  "group/alert relative grid w-full items-start gap-x-[var(--space-3)] gap-y-[var(--space-1)] rounded-[var(--radius-lg)] border p-[var(--space-4)] text-left font-sans transition-[background-color,border-color,color,box-shadow] duration-fast ease-standard motion-reduce:transition-none grid-cols-[auto_1fr_auto] [&>svg]:mt-[var(--space-0-5)] [&>svg:not([class*='size-'])]:size-[var(--icon-size-md)] [&>svg_path]:[stroke-width:var(--stroke-width-icon)] [&>svg_circle]:[stroke-width:var(--stroke-width-icon)] [&>svg_line]:[stroke-width:var(--stroke-width-icon)]",
  {
    variants: {
      variant: {
        default:
          "border-border bg-card text-foreground [&>svg]:text-muted-foreground [&_[data-slot=alert-dismiss]]:text-muted-foreground",
        info: "border-info bg-info-soft text-info [&>svg]:text-info [&_[data-slot=alert-title]]:text-info [&_[data-slot=alert-description]]:text-info [&_[data-slot=alert-dismiss]]:text-info",
        success:
          "border-success bg-success-soft text-success [&>svg]:text-success [&_[data-slot=alert-title]]:text-success [&_[data-slot=alert-description]]:text-success [&_[data-slot=alert-dismiss]]:text-success",
        warning:
          "border-warning bg-warning-soft text-warning [&>svg]:text-warning [&_[data-slot=alert-title]]:text-warning [&_[data-slot=alert-description]]:text-warning [&_[data-slot=alert-dismiss]]:text-warning",
        destructive:
          "border-destructive bg-destructive-soft text-destructive [&>svg]:text-destructive [&_[data-slot=alert-title]]:text-destructive [&_[data-slot=alert-description]]:text-destructive [&_[data-slot=alert-dismiss]]:text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return <div data-slot="alert" className={cn(alertVariants({ variant }), className)} {...props} />
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "font-[weight:var(--font-weight-medium)] text-[length:var(--text-title-sm)] leading-[var(--text-title-sm--line-height)] col-start-1 group-has-[>svg]/alert:col-start-2",
        className,
      )}
      {...props}
    />
  )
}

function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] font-[weight:var(--font-weight-regular)] text-balance text-muted-foreground col-start-1 group-has-[>svg]/alert:col-start-2 md:text-pretty [&_a]:underline [&_a]:underline-offset-3 [&_p:not(:last-child)]:mb-4",
        className,
      )}
      {...props}
    />
  )
}

function AlertAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-action"
      className={cn(
        "mt-[var(--space-3)] flex flex-wrap items-center gap-[var(--space-3)] col-start-1 group-has-[>svg]/alert:col-start-2",
        className,
      )}
      {...props}
    />
  )
}

function AlertDismiss({
  className,
  type = "button",
  "aria-label": ariaLabel = "Dismiss",
  ...props
}: React.ComponentProps<"button">) {
  return (
    <button
      aria-label={ariaLabel}
      className={cn(
        // hover/active 的文字色带 !:变体在祖先上声明 dismiss 颜色,与 :hover 同
        // 特异性 (0,2,0) 且生成顺序靠后,无 ! 会被压掉(实测 tailwindcss 4.3.3 输出)。
        "inline-flex size-[var(--icon-size-sm)] shrink-0 cursor-pointer items-center justify-center rounded-[var(--radius-full)] p-0 outline-none transition-[background-color,color,box-shadow] duration-fast ease-standard motion-reduce:transition-none col-start-2 row-start-1 group-has-[>svg]/alert:col-start-3 hover:bg-accent hover:text-accent-foreground! active:bg-[var(--selected-bg)] active:text-[var(--foreground-active)]! focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=hover]:bg-accent data-[state=hover]:text-accent-foreground! data-[state=active]:bg-[var(--selected-bg)] data-[state=active]:text-[var(--foreground-active)]! data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] [&_svg:not([class*='size-'])]:size-[var(--icon-size-xs)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
        className,
      )}
      data-slot="alert-dismiss"
      type={type}
      {...props}
    />
  )
}

export { Alert, AlertAction, AlertDescription, AlertDismiss, AlertTitle, alertVariants }
