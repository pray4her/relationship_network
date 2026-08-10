"use client"

import { AlertDialog as AlertDialogPrimitive } from "@base-ui/react/alert-dialog"
import { cva } from "class-variance-authority"
import { XIcon } from "lucide-react"
import type * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/dialog.css 的 confirmation / destructive confirmation
 * 变体(showcase/dialog.html 为唯一标准)。AlertDialog 固定对应规格的确认场景:
 * Base UI primitive 自带 role="alertdialog",且默认不响应 overlay 点击关闭(规格的
 * data-overlay-close="false"),Escape 仍允许。
 *
 * API → 规格映射:
 * - size:default → 规格 md(max-width calc(--space-16 × 8),默认 padding);
 *   sm → 规格 sm(紧凑 padding,title/body 降一档字号);
 *   lg 为规格有而旧 API 没有的尺寸,作为可选值新增。
 * - variant(新增可选):default → .dialog--confirmation(无额外着色);
 *   destructive → .dialog--destructive(surface 边框与 title 用 --destructive,
 *   提交动作由调用方给 AlertDialogAction 传 variant="destructive")。
 * - AlertDialogMedia 在规格解剖中无对应物,保留导出兼容旧 API,仅做 token 化。
 * 生命周期经 Base UI data-starting-style / data-ending-style 镜像规格的
 * dialog--opening / dialog--closing:半透明 --opacity-disabled + --space-2 下沉位移,
 * closing 切换 --duration-fast;motion-reduce 下动效移除(规格 REDUCED MOTION 条款)。
 */
const alertDialogContentVariants = cva(
  "group/alert-dialog-content fixed inset-0 isolate z-[var(--z-popover)] m-auto flex h-fit w-[calc(100%-var(--space-6)*2)] max-h-[calc(100%-var(--space-6)*2)] translate-y-0 flex-col overflow-hidden rounded-[var(--radius-xl)] border-[length:var(--border-width)] border-border bg-popover text-popover-foreground opacity-100 shadow-lift outline-none transition-[opacity,translate,box-shadow] duration-[var(--duration-normal)] ease-standard focus-visible:shadow-[var(--shadow-lift),0_0_0_var(--ring-width)_var(--ring-focus)] data-[ending-style]:translate-y-[var(--space-2)] data-[starting-style]:translate-y-[var(--space-2)] data-[ending-style]:opacity-[var(--opacity-disabled)] data-[starting-style]:opacity-[var(--opacity-disabled)] data-[ending-style]:duration-[var(--duration-fast)] data-[state=focus-visible]:shadow-[var(--shadow-lift),0_0_0_var(--ring-width)_var(--ring-focus)] motion-reduce:transition-none motion-reduce:data-[ending-style]:translate-y-0 motion-reduce:data-[starting-style]:translate-y-0",
  {
    variants: {
      size: {
        default: "max-w-[calc(var(--space-16)*8)]",
        sm: "max-w-[calc(var(--space-16)*6)]",
        lg: "max-w-[calc(var(--space-16)*12)]",
      },
      variant: {
        default: "",
        destructive: "border-destructive",
      },
    },
    defaultVariants: {
      size: "default",
      variant: "default",
    },
  },
)

function AlertDialog({ ...props }: AlertDialogPrimitive.Root.Props) {
  return <AlertDialogPrimitive.Root data-slot="alert-dialog" {...props} />
}

function AlertDialogTrigger({ ...props }: AlertDialogPrimitive.Trigger.Props) {
  return <AlertDialogPrimitive.Trigger data-slot="alert-dialog-trigger" {...props} />
}

function AlertDialogPortal({ ...props }: AlertDialogPrimitive.Portal.Props) {
  return <AlertDialogPrimitive.Portal data-slot="alert-dialog-portal" {...props} />
}

function AlertDialogOverlay({ className, ...props }: AlertDialogPrimitive.Backdrop.Props) {
  return (
    <AlertDialogPrimitive.Backdrop
      data-slot="alert-dialog-overlay"
      className={cn(
        "fixed inset-0 isolate z-[var(--z-popover)] bg-scrim opacity-100 transition-opacity duration-[var(--duration-normal)] ease-standard data-[ending-style]:opacity-[var(--opacity-disabled)] data-[starting-style]:opacity-[var(--opacity-disabled)] data-[ending-style]:duration-[var(--duration-fast)] motion-reduce:transition-none",
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogContent({
  className,
  size = "default",
  variant = "default",
  ...props
}: AlertDialogPrimitive.Popup.Props & {
  size?: "default" | "sm" | "lg"
  variant?: "default" | "destructive"
}) {
  return (
    <AlertDialogPortal>
      <AlertDialogOverlay />
      <AlertDialogPrimitive.Popup
        data-slot="alert-dialog-content"
        data-size={size}
        data-variant={variant}
        className={cn(alertDialogContentVariants({ size, variant }), className)}
        {...props}
      />
    </AlertDialogPortal>
  )
}

function AlertDialogHeader({
  className,
  children,
  showCloseButton = true,
  ...props
}: React.ComponentProps<"div"> & {
  /** 规格解剖:header = heading cluster + 组合的 IconButton 关闭控件。 */
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="alert-dialog-header"
      className={cn(
        "flex items-start gap-[var(--space-4)] border-border-soft border-b-[length:var(--border-width)] p-[var(--space-6)] group-data-[size=lg]/alert-dialog-content:p-[var(--space-8)] group-data-[size=sm]/alert-dialog-content:p-[var(--space-4)]",
        className,
      )}
      {...props}
    >
      <div data-slot="alert-dialog-heading" className="grid min-w-0 flex-1 gap-[var(--space-2)]">
        {children}
      </div>
      {showCloseButton && (
        <AlertDialogPrimitive.Close
          data-slot="alert-dialog-close"
          render={<Button className="flex-none" size="icon-sm" variant="ghost" />}
        >
          <XIcon />
          <span className="sr-only">Close</span>
        </AlertDialogPrimitive.Close>
      )}
    </div>
  )
}

function AlertDialogBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-dialog-body"
      className={cn(
        "grid min-h-0 gap-[var(--space-4)] overflow-y-auto overscroll-contain p-[var(--space-6)] font-sans text-[length:var(--text-body-md)] text-foreground-body leading-[var(--text-body-md--line-height)] group-data-[size=lg]/alert-dialog-content:p-[var(--space-8)] group-data-[size=sm]/alert-dialog-content:p-[var(--space-4)] group-data-[size=sm]/alert-dialog-content:text-[length:var(--text-body-sm)] group-data-[size=sm]/alert-dialog-content:leading-[var(--text-body-sm--line-height)] [&>*]:m-0",
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-dialog-footer"
      className={cn(
        "flex flex-none flex-wrap justify-end gap-[var(--space-3)] border-border-soft border-t-[length:var(--border-width)] bg-surface-soft px-[var(--space-6)] py-[var(--space-4)] group-data-[size=lg]/alert-dialog-content:px-[var(--space-8)] group-data-[size=sm]/alert-dialog-content:px-[var(--space-4)] group-data-[size=lg]/alert-dialog-content:py-[var(--space-6)] group-data-[size=sm]/alert-dialog-content:py-[var(--space-3)]",
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogMedia({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-dialog-media"
      className={cn(
        "mb-[var(--space-2)] inline-flex size-[calc(var(--space-4)*2.5)] items-center justify-center rounded-[var(--radius-md)] bg-surface-soft [&_svg:not([class*='size-'])]:size-[var(--icon-size-lg)]",
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogTitle({ className, ...props }: AlertDialogPrimitive.Title.Props) {
  return (
    <AlertDialogPrimitive.Title
      data-slot="alert-dialog-title"
      className={cn(
        "font-sans font-medium text-[length:var(--text-title-lg)] text-foreground leading-[var(--text-title-lg--line-height)] group-data-[size=sm]/alert-dialog-content:text-[length:var(--text-title-md)] group-data-[size=sm]/alert-dialog-content:leading-[var(--text-title-md--line-height)] group-data-[variant=destructive]/alert-dialog-content:text-destructive",
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogDescription({ className, ...props }: AlertDialogPrimitive.Description.Props) {
  return (
    <AlertDialogPrimitive.Description
      data-slot="alert-dialog-description"
      className={cn(
        "font-sans text-[length:var(--text-body-sm)] text-muted-foreground leading-[var(--text-body-sm--line-height)] *:[a]:underline *:[a]:underline-offset-[var(--link-underline-offset)] *:[a]:hover:text-foreground",
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogAction({ className, ...props }: React.ComponentProps<typeof Button>) {
  return <Button data-slot="alert-dialog-action" className={cn(className)} {...props} />
}

function AlertDialogCancel({
  className,
  variant = "outline",
  size = "default",
  ...props
}: AlertDialogPrimitive.Close.Props &
  Pick<React.ComponentProps<typeof Button>, "variant" | "size">) {
  return (
    <AlertDialogPrimitive.Close
      data-slot="alert-dialog-cancel"
      className={cn(className)}
      render={<Button variant={variant} size={size} />}
      {...props}
    />
  )
}

export {
  AlertDialog,
  AlertDialogAction,
  AlertDialogBody,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogTitle,
  AlertDialogTrigger,
}
