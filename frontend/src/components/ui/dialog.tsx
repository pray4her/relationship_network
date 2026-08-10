"use client"

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { cva, type VariantProps } from "class-variance-authority"
import { XIcon } from "lucide-react"
import type * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/dialog.css(showcase/dialog.html 为唯一标准)。
 *
 * API → 规格映射:
 * - size:    default→md(surface max-width --space-16×8、padding --space-6)、
 *            sm→--space-16×6/padding --space-4、lg→--space-16×12/padding --space-8。
 * - variant: default→standard;confirmation/destructive→role="alertdialog";
 *            destructive 额外把 surface 边框与标题着色为 --destructive。
 *            规格的 data-overlay-close="false" 对应 Root 的 disablePointerDismissal。
 * - 关闭按钮: 规格的 .icon-btn + .icon--muted + .icon--sm 组合 →
 *            Button(variant="ghost" size="icon") + text-muted-foreground;
 *            showcase lg 行的 icon--md 统一收敛到 icon 规格,不新增尺寸。
 * - 生命周期: opening/closing 帧(半透明 + --space-2 下移)由 base-ui 的
 *            data-starting-style/data-ending-style 承载(closing 切 --duration-fast);
 *            data-[state=opening|closing] 为同帧静态镜像,供预览页截图。
 * - surface 兜底聚焦环:focus-visible 伪类 + data-[state=focus-visible] 镜像,
 *            保持 --shadow-lift 同时叠加 --ring-width/--ring-focus。
 */

const dialogOverlayVariants = cva(
  "fixed inset-0 z-[var(--z-popover)] bg-scrim transition-opacity duration-normal ease-standard data-starting-style:opacity-[var(--opacity-disabled)] data-ending-style:opacity-[var(--opacity-disabled)] data-ending-style:duration-fast data-[state=opening]:opacity-[var(--opacity-disabled)] data-[state=closing]:opacity-[var(--opacity-disabled)] motion-reduce:transition-none",
)

const dialogContentVariants = cva(
  "group/dialog fixed inset-0 z-[var(--z-popover)] m-auto flex h-fit w-[calc(100%-var(--space-6)*2)] max-h-[calc(100%-var(--space-6)*2)] flex-col overflow-hidden rounded-[var(--radius-xl)] border border-border bg-popover text-popover-foreground shadow-lift outline-none transition-[opacity,translate,box-shadow] duration-normal ease-standard focus-visible:shadow-[var(--shadow-lift),0_0_0_var(--ring-width)_var(--ring-focus)] data-starting-style:translate-y-[var(--space-2)] data-starting-style:opacity-[var(--opacity-disabled)] data-ending-style:translate-y-[var(--space-2)] data-ending-style:opacity-[var(--opacity-disabled)] data-ending-style:duration-fast data-[state=focus-visible]:shadow-[var(--shadow-lift),0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=opening]:translate-y-[var(--space-2)] data-[state=opening]:opacity-[var(--opacity-disabled)] data-[state=closing]:translate-y-[var(--space-2)] data-[state=closing]:opacity-[var(--opacity-disabled)] motion-reduce:transition-none",
  {
    variants: {
      variant: {
        default: "",
        confirmation: "",
        destructive: "border-destructive",
      },
      size: {
        default: "max-w-[calc(var(--space-16)*8)]",
        sm: "max-w-[calc(var(--space-16)*6)]",
        lg: "max-w-[calc(var(--space-16)*12)]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

/** 关闭按钮定位钩(规格的 .dialog__close):对齐各 size 的 header padding。 */
const dialogCloseVariants = cva(
  "absolute top-[var(--space-6)] right-[var(--space-6)] text-muted-foreground group-data-[size=sm]/dialog:top-[var(--space-4)] group-data-[size=sm]/dialog:right-[var(--space-4)] group-data-[size=lg]/dialog:top-[var(--space-8)] group-data-[size=lg]/dialog:right-[var(--space-8)]",
)

function Dialog({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({ ...props }: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({ ...props }: DialogPrimitive.Portal.Props) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({ ...props }: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({ className, ...props }: DialogPrimitive.Backdrop.Props) {
  return (
    <DialogPrimitive.Backdrop
      className={cn(dialogOverlayVariants(), className)}
      data-slot="dialog-overlay"
      {...props}
    />
  )
}

type DialogContentProps = DialogPrimitive.Popup.Props &
  VariantProps<typeof dialogContentVariants> & {
    /** 是否在 header 区渲染规格的 icon 关闭按钮。 */
    showCloseButton?: boolean
  }

function DialogContent({
  className,
  children,
  size = "default",
  variant = "default",
  showCloseButton = true,
  ...props
}: DialogContentProps) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Popup
        className={cn(dialogContentVariants({ size, variant }), className)}
        data-size={size}
        data-slot="dialog-content"
        data-variant={variant}
        role={variant === "default" ? undefined : "alertdialog"}
        {...props}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            data-slot="dialog-close"
            render={<Button className={dialogCloseVariants()} size="icon" variant="ghost" />}
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Popup>
    </DialogPortal>
  )
}

function DialogHeader({ className, children, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex items-start gap-[var(--space-4)] border-border-soft border-b p-[var(--space-6)] group-data-[size=sm]/dialog:p-[var(--space-4)] group-data-[size=lg]/dialog:p-[var(--space-8)]",
        className,
      )}
      data-slot="dialog-header"
      {...props}
    >
      <div className="grid min-w-0 flex-1 gap-[var(--space-2)]" data-slot="dialog-heading">
        {children}
      </div>
    </div>
  )
}

/** 规格的 .dialog__body:可滚动主内容区。 */
function DialogBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "grid min-h-0 flex-1 gap-[var(--space-4)] overflow-y-auto overscroll-contain p-[var(--space-6)] font-sans text-base font-normal text-foreground-body group-data-[size=sm]/dialog:p-[var(--space-4)] group-data-[size=sm]/dialog:text-sm group-data-[size=lg]/dialog:p-[var(--space-8)] [&>*]:m-0",
        className,
      )}
      data-slot="dialog-body"
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      className={cn(
        "flex flex-none flex-wrap items-center justify-end gap-[var(--space-3)] border-border-soft border-t bg-surface-soft px-[var(--space-6)] py-[var(--space-4)] group-data-[size=sm]/dialog:px-[var(--space-4)] group-data-[size=sm]/dialog:py-[var(--space-3)] group-data-[size=lg]/dialog:px-[var(--space-8)] group-data-[size=lg]/dialog:py-[var(--space-6)]",
        className,
      )}
      data-slot="dialog-footer"
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close render={<Button variant="outline" />}>Close</DialogPrimitive.Close>
      )}
    </div>
  )
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      className={cn(
        "font-sans text-title-lg font-medium text-foreground group-data-[size=sm]/dialog:text-title-md group-data-[variant=destructive]/dialog:text-destructive",
        className,
      )}
      data-slot="dialog-title"
      {...props}
    />
  )
}

function DialogDescription({ className, ...props }: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      className={cn(
        "font-sans text-sm font-normal text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
        className,
      )}
      data-slot="dialog-description"
      {...props}
    />
  )
}

export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
  dialogCloseVariants,
  dialogContentVariants,
  dialogOverlayVariants,
}
