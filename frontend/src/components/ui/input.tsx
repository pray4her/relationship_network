import { Input as InputPrimitive } from "@base-ui/react/input"
import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/input.css(showcase 为唯一标准)。
 * 结构合同:.input-wrap 拥有全部状态样式(border / focus ring / disabled / readonly),
 * 原生控件无 chrome、透明、填满 wrap;纯文本输入即"只有一个子节点的 wrap"。
 * 状态一律从控件读取(:has / :focus-within,规格明确不在 wrap 上重复状态);
 * 静态镜像同样经 has- 读取控件上的 data-[state=hover|focus-visible|error|success],
 * 预览页可静态渲染 hover/focus/error/success 态。focus 环遵循规格:任何进入方式
 * (键盘或鼠标)都显示,等价于 wrap 的 :focus-within。
 *
 * API 映射与规格缺口:
 * - size 为新增可选 prop:sm → --control-height-sm + --text-body-sm,
 *   lg → --control-height-lg(规格中 lg 不改字号),default → --control-height。
 * - leadingIcon / trailingIcon / prefix / suffix 为新增可选 prop,
 *   对应规格 .input__icon / .input__prefix / .input__suffix(图标装饰性,aria-hidden)。
 * - error 态走原生 aria-invalid(FormField 合同,规格 .input-wrap--error 与之配对);
 *   success 态无原生属性,规格类 .input-wrap--success 映射为控件上的
 *   data-state="success"。
 * - 规格 .input__clear 清除按钮未实现:需要受控值行为,showcase 未演示,留作后续。
 * - type="file" 规格未定义,file: 伪元素样式映射到最近 token(无边框、前景色、
 *   中字重),保持既有上传调用处可用。
 * - 原生 input 的 size(number)与 prefix(string)属性被同名 prop 占用,已 Omit。
 */
const inputWrapVariants = cva(
  "flex w-full items-center gap-[var(--space-2)] rounded-[var(--radius-md)] border-[length:var(--border-width)] border-solid border-input bg-background px-[var(--input-padding-inline)] transition-[border-color,box-shadow] duration-fast ease-standard hover:border-border-strong has-[:disabled]:hover:border-input has-[[data-state=hover]]:border-border-strong focus-within:border-primary focus-within:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] has-[[data-state=focus-visible]]:border-primary has-[[data-state=focus-visible]]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] has-[[aria-invalid=true]]:border-destructive has-[[aria-invalid=true]]:focus-within:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] has-[[data-state=error]]:border-destructive has-[[data-state=error]]:focus-within:shadow-[0_0_0_var(--ring-width)_var(--ring-destructive)] has-[[data-state=success]]:border-success has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-[var(--opacity-disabled)] has-[:read-only]:bg-muted",
  {
    variants: {
      size: {
        sm: "h-[var(--control-height-sm)]",
        default: "h-[var(--control-height)]",
        lg: "h-[var(--control-height-lg)]",
      },
    },
    defaultVariants: {
      size: "default",
    },
  },
)

/** 控件字号:sm → --text-body-sm;default/lg → --text-body-md(规格 lg 只改高度)。 */
const controlTextBySize = {
  sm: "text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)]",
  default: "text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)]",
  lg: "text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)]",
} as const

/** 原生控件:无 chrome,填满 wrap;状态样式全在 wrap 上(见 inputWrapVariants)。 */
const controlBaseClass =
  "h-full min-w-0 flex-1 border-0 bg-transparent p-0 font-sans text-foreground outline-none placeholder:text-caption-foreground disabled:cursor-not-allowed file:inline-flex file:items-center file:border-0 file:bg-transparent file:pe-[var(--space-2)] file:font-medium file:text-foreground [&::-webkit-inner-spin-button]:m-0 [&::-webkit-outer-spin-button]:m-0"

/** .input__icon:装饰性、安静(--caption-foreground),共享图标尺寸与描边 token。 */
const iconClass =
  "flex-none text-caption-foreground [&_svg]:block [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]"

type InputProps = Omit<React.ComponentProps<"input">, "prefix" | "size"> &
  VariantProps<typeof inputWrapVariants> & {
    /** 前导装饰图标(规格 .input__icon,aria-hidden)。 */
    leadingIcon?: React.ReactNode
    /** 后随装饰图标(规格 .input__icon,aria-hidden)。 */
    trailingIcon?: React.ReactNode
    /** 文本前缀(规格 .input__prefix,如 "$")。 */
    prefix?: React.ReactNode
    /** 文本后缀(规格 .input__suffix,如 "USD / hr")。 */
    suffix?: React.ReactNode
  }

function Input({
  className,
  size = "default",
  type,
  leadingIcon,
  trailingIcon,
  prefix,
  suffix,
  ...props
}: InputProps) {
  const textSize = controlTextBySize[size ?? "default"]
  return (
    <div className={cn(inputWrapVariants({ size }), className)} data-slot="input-wrap">
      {leadingIcon ? (
        <span aria-hidden="true" className={iconClass} data-slot="input-icon">
          {leadingIcon}
        </span>
      ) : null}
      {prefix ? (
        <span
          className={cn("flex-none select-none text-muted-foreground", textSize)}
          data-slot="input-prefix"
        >
          {prefix}
        </span>
      ) : null}
      <InputPrimitive
        className={cn(controlBaseClass, textSize)}
        data-slot="input"
        type={type}
        {...props}
      />
      {suffix ? (
        <span
          className={cn("flex-none select-none text-muted-foreground", textSize)}
          data-slot="input-suffix"
        >
          {suffix}
        </span>
      ) : null}
      {trailingIcon ? (
        <span aria-hidden="true" className={iconClass} data-slot="input-icon">
          {trailingIcon}
        </span>
      ) : null}
    </div>
  )
}

export { Input, inputWrapVariants }
