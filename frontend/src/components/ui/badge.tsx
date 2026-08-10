import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps, MouseEventHandler } from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/badge.css(showcase/badge.html 为唯一标准)。
 * 非交互状态标签(<span>;唯一可聚焦部件是可选的 dismiss 按钮)。
 * variant 是语义角色,解析到语义状态 token;subtle/solid/outline 三种 style
 * 共享同一外框几何(恒定 --border-width 描边,不用时透明)。
 *
 * 现有 API → 规格映射(规格无同名物时映射到最近规格):
 *   variant=default     → solid primary(原为 primary 实底)
 *   variant=secondary   → subtle neutral(中性 --card 底)
 *   variant=ghost       → subtle neutral(规格无 ghost,取最近的中性 subtle)
 *   variant=destructive → subtle destructive(原为 destructive 浅底文字)
 *   variant=outline     → outline neutral(中性 --border 描边)
 *   variant=link        → outline primary(规格无 link,primary 由描边 + accent 表达)
 * 规格原生的 variant(neutral/primary/success/warning/destructive/info)×
 * style(subtle/solid/outline)与 size(sm,--text-caption-up 大写处理)为新增
 * 可选能力;默认 default/subtle/md 与迁移前渲染一致。
 * dismiss 交互态同时挂伪类与 data-[state=*] 镜像,预览页可静态渲染。
 */

/* 完整配方(背景/文字/描边/accent/dismiss 一次给齐,不跨选择器覆盖,避免冲突)。 */
const subtleNeutral =
  "border-transparent bg-card text-foreground [--_badge-accent:var(--muted-foreground)] [--_badge-dismiss:var(--muted-foreground)]"
const subtlePrimary =
  "border-transparent bg-card text-foreground [--_badge-accent:var(--primary)] [--_badge-dismiss:var(--muted-foreground)]"
const subtleSuccess =
  "border-transparent bg-success-soft text-foreground [--_badge-accent:var(--success)] [--_badge-dismiss:var(--muted-foreground)]"
const subtleWarning =
  "border-transparent bg-warning-soft text-foreground [--_badge-accent:var(--warning)] [--_badge-dismiss:var(--muted-foreground)]"
const subtleDestructive =
  "border-transparent bg-destructive-soft text-foreground [--_badge-accent:var(--destructive)] [--_badge-dismiss:var(--muted-foreground)]"
const subtleInfo =
  "border-transparent bg-info-soft text-foreground [--_badge-accent:var(--info)] [--_badge-dismiss:var(--muted-foreground)]"

const solidNeutral =
  "border-transparent bg-surface-cream-strong text-foreground [--_badge-accent:var(--foreground)] [--_badge-dismiss:var(--foreground)]"
const solidPrimary =
  "border-transparent bg-primary text-primary-foreground [--_badge-accent:var(--primary-foreground)] [--_badge-dismiss:var(--primary-foreground)]"
const solidSuccess =
  "border-transparent bg-success text-success-foreground [--_badge-accent:var(--success-foreground)] [--_badge-dismiss:var(--success-foreground)]"
const solidWarning =
  "border-transparent bg-warning text-warning-foreground [--_badge-accent:var(--warning-foreground)] [--_badge-dismiss:var(--warning-foreground)]"
const solidDestructive =
  "border-transparent bg-destructive text-destructive-foreground [--_badge-accent:var(--destructive-foreground)] [--_badge-dismiss:var(--destructive-foreground)]"
const solidInfo =
  "border-transparent bg-info text-info-foreground [--_badge-accent:var(--info-foreground)] [--_badge-dismiss:var(--info-foreground)]"

const outlineNeutral =
  "border-border bg-transparent text-foreground [--_badge-accent:var(--muted-foreground)] [--_badge-dismiss:var(--muted-foreground)]"
const outlinePrimary =
  "border-primary bg-transparent text-foreground [--_badge-accent:var(--primary)] [--_badge-dismiss:var(--muted-foreground)]"
const outlineSuccess =
  "border-success bg-transparent text-foreground [--_badge-accent:var(--success)] [--_badge-dismiss:var(--muted-foreground)]"
const outlineWarning =
  "border-warning bg-transparent text-foreground [--_badge-accent:var(--warning)] [--_badge-dismiss:var(--muted-foreground)]"
const outlineDestructive =
  "border-destructive bg-transparent text-foreground [--_badge-accent:var(--destructive)] [--_badge-dismiss:var(--muted-foreground)]"
const outlineInfo =
  "border-info bg-transparent text-foreground [--_badge-accent:var(--info)] [--_badge-dismiss:var(--muted-foreground)]"

const badgeVariants = cva(
  "group/badge inline-flex w-fit shrink-0 items-center rounded-[var(--radius-full)] border-[length:var(--border-width)] border-solid font-sans font-medium whitespace-nowrap select-none transition-[background-color,color,border-color] duration-fast ease-standard motion-reduce:transition-none [&_[data-slot=badge-dot]]:size-[var(--space-2)] [&_[data-slot=badge-dot]]:shrink-0 [&_[data-slot=badge-dot]]:rounded-[var(--radius-full)] [&_[data-slot=badge-dot]]:bg-[color:var(--_badge-accent)] [&>svg]:pointer-events-none [&>svg]:size-[var(--icon-size-xs)] [&>svg]:shrink-0 [&>svg]:text-[color:var(--_badge-accent)] [&>svg_circle]:[stroke-width:var(--stroke-width-icon)] [&>svg_path]:[stroke-width:var(--stroke-width-icon)]",
  {
    variants: {
      variant: {
        /* 规格原生 variant:颜色全部在 compoundVariants(variant × style)中给出。 */
        neutral: "",
        primary: "",
        success: "",
        warning: "",
        destructive: "",
        info: "",
        /* 现有 API 别名 → 最近规格配方(映射见上方注释)。 */
        default: solidPrimary,
        secondary: subtleNeutral,
        ghost: subtleNeutral,
        outline: outlineNeutral,
        link: outlinePrimary,
      },
      style: {
        subtle: "",
        solid: "",
        outline: "",
      },
      size: {
        default:
          "gap-[var(--space-2)] px-[var(--space-3)] py-[var(--space-1)] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)]",
        sm: "gap-[var(--space-1)] px-[var(--space-2)] py-[var(--space-0-5)] text-[length:var(--text-caption-up)] uppercase leading-[var(--text-caption-up--line-height)] tracking-[var(--text-caption-up--letter-spacing)]",
      },
    },
    compoundVariants: [
      { variant: "neutral", style: "subtle", class: subtleNeutral },
      { variant: "primary", style: "subtle", class: subtlePrimary },
      { variant: "success", style: "subtle", class: subtleSuccess },
      { variant: "warning", style: "subtle", class: subtleWarning },
      { variant: "destructive", style: "subtle", class: subtleDestructive },
      { variant: "info", style: "subtle", class: subtleInfo },
      { variant: "neutral", style: "solid", class: solidNeutral },
      { variant: "primary", style: "solid", class: solidPrimary },
      { variant: "success", style: "solid", class: solidSuccess },
      { variant: "warning", style: "solid", class: solidWarning },
      { variant: "destructive", style: "solid", class: solidDestructive },
      { variant: "info", style: "solid", class: solidInfo },
      { variant: "neutral", style: "outline", class: outlineNeutral },
      { variant: "primary", style: "outline", class: outlinePrimary },
      { variant: "success", style: "outline", class: outlineSuccess },
      { variant: "warning", style: "outline", class: outlineWarning },
      { variant: "destructive", style: "outline", class: outlineDestructive },
      { variant: "info", style: "outline", class: outlineInfo },
    ],
    defaultVariants: {
      variant: "default",
      style: "subtle",
      size: "default",
    },
  },
)

/** dismiss 按钮:规格唯一可交互部件,颜色经 --_badge-dismiss 别名随配方走。 */
const badgeDismissClasses =
  "inline-flex size-[var(--icon-size-sm)] shrink-0 cursor-pointer items-center justify-center rounded-[var(--radius-full)] border-0 bg-transparent p-0 text-[color:var(--_badge-dismiss)] transition-[background-color,color,box-shadow] duration-fast ease-standard outline-none hover:bg-accent hover:text-accent-foreground active:bg-[var(--selected-bg)] active:text-[color:var(--foreground-active)] focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=hover]:bg-accent data-[state=hover]:text-accent-foreground data-[state=active]:bg-[var(--selected-bg)] data-[state=active]:text-[color:var(--foreground-active)] data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] motion-reduce:transition-none [&_svg]:size-[var(--icon-size-xs)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]"

type BadgeProps = useRender.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & {
    /** 状态点:渲染规格的 badge__dot(--space-2 圆点,颜色取 variant 的 accent token)。 */
    dot?: boolean
    /** 可移除徽章:渲染规格的 dismiss 按钮(markup 合同:<button aria-label="Remove …">)。 */
    onDismiss?: MouseEventHandler<HTMLButtonElement>
    /** dismiss 按钮的 aria-label。 */
    dismissLabel?: string
    /** 透传给 dismiss 按钮的其余属性(预览页用 data-state 静态渲染交互态)。 */
    dismissProps?: Omit<ComponentProps<"button">, "children" | "className" | "onClick" | "type"> & {
      [dataAttribute: `data-${string}`]: string | undefined
    }
  }

function Badge({
  className,
  variant = "default",
  style = "subtle",
  size = "default",
  dot,
  onDismiss,
  dismissLabel,
  dismissProps,
  render,
  children,
  ...props
}: BadgeProps) {
  const dismissible = onDismiss !== undefined || dismissProps !== undefined
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant, style, size }), className),
        children: (
          <>
            {dot && <span data-slot="badge-dot" role="presentation" />}
            {children}
            {dismissible && (
              <button
                aria-label={dismissLabel ?? "Remove"}
                className={badgeDismissClasses}
                data-slot="badge-dismiss"
                onClick={onDismiss}
                type="button"
                {...dismissProps}
              >
                <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
                  <path d="m7 7 10 10M17 7 7 17" stroke="currentColor" strokeLinecap="round" />
                </svg>
              </button>
            )}
          </>
        ),
      },
      props,
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
