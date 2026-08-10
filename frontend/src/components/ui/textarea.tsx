import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/textarea.css(showcase/textarea.html 为唯一标准),
 * 与 Input 共享全部语义 field token。
 * 状态同时挂伪类与 data-[state=*] 镜像,预览页可静态渲染 hover/focus/success 态:
 * - hover 镜像 data-[state=hover](伪类限定 :not(:disabled))
 * - focus 镜像 data-[state=focus] / data-[state=focus-visible](规格在 :focus 上宣告焦点)
 * - success 无 aria 对应物,规格用 .textarea--success 类,这里镜像为 data-[state=success]
 * - error 走原生 aria-invalid(等价于规格的 .textarea--error / [aria-invalid="true"])
 * resize 是行为而非视觉值:默认 resize-y, opt out/in 直接用 Tailwind 的
 * resize-none / resize-both 工具类(对应规格的 .textarea--resize-none/--resize-both)。
 */
const textareaVariants = cva(
  "block w-full resize-y rounded-[var(--radius-md)] border border-input bg-background px-[var(--input-padding-inline)] py-[var(--input-padding-block)] font-sans text-foreground outline-none transition-[border-color,box-shadow] duration-fast ease-standard placeholder:text-caption-foreground not-disabled:hover:border-border-strong focus:border-primary focus:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] disabled:cursor-not-allowed disabled:resize-none disabled:opacity-[var(--opacity-disabled)] read-only:bg-muted aria-invalid:border-destructive aria-invalid:focus:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] data-[state=hover]:border-border-strong data-[state=focus]:border-primary data-[state=focus]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=focus-visible]:border-primary data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=success]:border-success motion-reduce:transition-none",
  {
    variants: {
      size: {
        sm: "min-h-[var(--textarea-min-height-sm)] text-sm",
        md: "min-h-[var(--textarea-min-height-md)] text-base",
        lg: "min-h-[var(--textarea-min-height-lg)] text-base",
      },
    },
    defaultVariants: {
      size: "md",
    },
  },
)

type TextareaProps = React.ComponentProps<"textarea"> & VariantProps<typeof textareaVariants>

function Textarea({ className, size = "md", ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(textareaVariants({ size }), className)}
      data-slot="textarea"
      {...props}
    />
  )
}

export { Textarea, textareaVariants }
