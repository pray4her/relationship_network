"use client"

import { cva } from "class-variance-authority"
import {
  CircleCheckIcon,
  CircleMinusIcon,
  CircleXIcon,
  InfoIcon,
  Loader2Icon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react"
import type { ReactNode } from "react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/toast.css(showcase/toast.html 为唯一标准)。
 *
 * 解析模型与规格一致:toast 本体声明 accent 别名(--toast-accent,即规格的 --_accent),
 * variant 只重声明该别名;中性 toast 走 var() fallback(--muted-foreground)。
 * 表面(--popover)、边框(--border)、阴影(--shadow-lift + inset 状态边)、
 * 文字(--foreground / --muted-foreground)在所有 variant 间共享。
 *
 * API 映射(sonner → 规格):
 * - sonner 没有 variant prop,toast 类型即 variant:default→neutral、error→destructive,
 *   info/success/warning 同名;loading 规格无对应 variant → 映射到最近规格 neutral。
 * - toast 的 action / cancel 按钮 → 规格要求 "compose real .btn":action 用 Button
 *   secondary/sm;cancel 规格未提及 → 映射到最近规格 ghost/sm。
 * - 生命周期(entering/visible/exiting)按规格由控制器驱动,sonner 自带堆叠/进出场
 *   位移即控制器实现;data-[state=entering|visible|exiting] 镜像仅供预览页静态渲染。
 * - 层叠:sonner 自带 z-index: 999999999,规格要求 --z-popover,已用内联 style 覆盖;
 *   规格自身报告了 --z-toast 缺口,当前按规格共享 --z-popover。
 * - 规格缺口:sonner 的 icons prop 没有 neutral/default 键,neutral 的 leading 图标
 *   无法注入运行时 toast(toastVariantIcons.neutral 仅预览页样品使用)。
 *
 * sonner 的 DOM 顺序是 close → icon → content → action,且 action 无法嵌进 body,
 * 与规格 anatomy(icon · body · close,action 在 body 内)不同:这里用 grid 的
 * order / col-start 复刻规格布局(action 落在 body 列下一行,行距 --space-3 加
 * mt --space-1,合计等于规格的 body gap --space-1 + action margin-top --space-3)。
 */
const toastVariants = cva(
  "group/toast relative grid w-full grid-cols-[auto_1fr_auto] items-start gap-[var(--space-3)] rounded-[var(--radius-lg)] border-[length:var(--border-width)] border-border bg-popover p-[var(--space-4)] font-sans text-foreground shadow-[var(--shadow-lift),inset_var(--border-width-strong)_0_0_var(--toast-accent,var(--muted-foreground))] data-[state=entering]:translate-y-[var(--space-4)] data-[state=entering]:opacity-0 data-[state=visible]:translate-y-0 data-[state=visible]:opacity-100 data-[state=exiting]:translate-y-[var(--space-4)] data-[state=exiting]:opacity-0 [&_[data-icon]]:text-[var(--toast-accent,var(--muted-foreground))]",
  {
    variants: {
      variant: {
        neutral: "",
        info: "[--toast-accent:var(--info)]",
        success: "[--toast-accent:var(--success)]",
        warning: "[--toast-accent:var(--warning)]",
        destructive: "[--toast-accent:var(--destructive)]",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
)

/** 规格各解剖部位的 token 类;close 的交互态同时挂伪类与 data-[state=*] 镜像。 */
const toastPartClassNames = {
  icon: "order-1 col-start-1 row-start-1 mt-[var(--space-0-5)] size-[var(--icon-size-md)] [&_svg]:size-full [&_svg_path]:[stroke-width:var(--stroke-width-icon)] [&_svg_circle]:[stroke-width:var(--stroke-width-icon)] [&_svg_line]:[stroke-width:var(--stroke-width-icon)]",
  content: "order-2 col-start-2 row-start-1 grid min-w-0 gap-[var(--space-1)]",
  title:
    "font-medium text-[length:var(--text-title-sm)] leading-[var(--text-title-sm--line-height)] text-foreground",
  description:
    "text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] text-muted-foreground",
  action: cn(
    buttonVariants({ variant: "secondary", size: "sm" }),
    "order-3 col-start-2 mt-[var(--space-1)]",
  ),
  cancel: cn(
    buttonVariants({ variant: "ghost", size: "sm" }),
    "order-3 col-start-2 mt-[var(--space-1)]",
  ),
  close:
    "order-4 col-start-3 row-start-1 inline-flex size-[var(--icon-size-sm)] cursor-pointer items-center justify-center rounded-[var(--radius-full)] text-muted-foreground outline-none transition-[background-color,color,box-shadow] duration-fast ease-standard hover:bg-accent hover:text-accent-foreground focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] active:bg-[var(--selected-bg)] active:text-[var(--foreground-active)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=hover]:bg-accent data-[state=hover]:text-accent-foreground data-[state=active]:bg-[var(--selected-bg)] data-[state=active]:text-[var(--foreground-active)] data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] [&_svg]:size-[var(--icon-size-xs)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
} as const

type ToastVariant = "neutral" | "info" | "success" | "warning" | "destructive"

/** 各 variant 的 leading status SVG(decorative,aria-hidden),与 showcase 字形一一对应。 */
const toastVariantIcons: Record<ToastVariant | "loading" | "close", ReactNode> = {
  neutral: <CircleMinusIcon aria-hidden="true" />,
  info: <InfoIcon aria-hidden="true" />,
  success: <CircleCheckIcon aria-hidden="true" />,
  warning: <TriangleAlertIcon aria-hidden="true" />,
  destructive: <CircleXIcon aria-hidden="true" />,
  loading: (
    <Loader2Icon
      aria-hidden="true"
      className="animate-spin [animation-duration:var(--duration-loading)] [animation-timing-function:linear]"
    />
  ),
  close: <XIcon aria-hidden="true" />,
}

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      className="toaster group"
      // = --space-3(12px):sonner 控制器只接受 px 数值参与堆叠位移计算,无法传 var()
      gap={12}
      icons={{
        success: toastVariantIcons.success,
        info: toastVariantIcons.info,
        warning: toastVariantIcons.warning,
        error: toastVariantIcons.destructive,
        loading: toastVariantIcons.loading,
        close: toastVariantIcons.close,
      }}
      mobileOffset="var(--space-6)"
      offset="var(--space-6)"
      position="bottom-right"
      style={
        {
          // 规格:viewport 层叠 = --z-popover;toast 宽度 = calc(--space-16 * 6)
          zIndex: "var(--z-popover)",
          "--width": "calc(var(--space-16) * 6)",
        } as React.CSSProperties
      }
      theme="light"
      toastOptions={{
        // sonner 自带皮肤与规格完全不同,unstyled 后全部视觉走语义 token 类
        unstyled: true,
        classNames: {
          toast: cn(toastVariants({ variant: "neutral" }), "cn-toast"),
          info: toastVariants({ variant: "info" }),
          success: toastVariants({ variant: "success" }),
          warning: toastVariants({ variant: "warning" }),
          error: toastVariants({ variant: "destructive" }),
          icon: toastPartClassNames.icon,
          content: toastPartClassNames.content,
          title: toastPartClassNames.title,
          description: toastPartClassNames.description,
          actionButton: toastPartClassNames.action,
          cancelButton: toastPartClassNames.cancel,
          closeButton: toastPartClassNames.close,
        },
      }}
      {...props}
    />
  )
}

export type { ToastVariant }
export { Toaster, toastPartClassNames, toastVariantIcons, toastVariants }
