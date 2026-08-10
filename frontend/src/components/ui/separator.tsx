"use client"

import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/separator.css(showcase 为唯一标准)。
 * 层级完全由语义 border 颜色(--border-soft/--border/--border-strong)与
 * 厚度(--border-width/--border-width-strong)token 表达,不施加透明度;
 * 外围间距固定为方向轴上的 --space-4。
 *
 * Separator 为非交互结构元素:规格无 hover/active/focus/disabled 态
 * (--opacity-disabled 预留给可禁用控件),因此没有伪类或 data-[state=*] 镜像。
 *
 * API 映射:规格样式 subtle/default/strong 新增为可选 variant prop(默认
 * default,与原 API 渲染颜色一致,现有调用处不受影响);orientation 沿用原
 * API;规格未定义 size。装饰性分隔线可直接透传 aria-hidden(见规格 Semantics)。
 */
const separatorVariants = cva("block flex-none border-none", {
  variants: {
    variant: {
      subtle: "bg-border-soft",
      default: "bg-border",
      strong: "bg-border-strong",
    },
    orientation: {
      horizontal: "my-[var(--space-4)] h-[var(--border-width)] w-full",
      vertical: "mx-[var(--space-4)] w-[var(--border-width)] self-stretch",
    },
  },
  compoundVariants: [
    {
      variant: "strong",
      orientation: "horizontal",
      class: "h-[var(--border-width-strong)]",
    },
    {
      variant: "strong",
      orientation: "vertical",
      class: "w-[var(--border-width-strong)]",
    },
  ],
  defaultVariants: {
    variant: "default",
    orientation: "horizontal",
  },
})

type SeparatorProps = SeparatorPrimitive.Props & VariantProps<typeof separatorVariants>

function Separator({
  className,
  variant = "default",
  orientation = "horizontal",
  ...props
}: SeparatorProps) {
  return (
    <SeparatorPrimitive
      className={cn(separatorVariants({ variant, orientation }), className)}
      data-slot="separator"
      orientation={orientation}
      {...props}
    />
  )
}

export { Separator, separatorVariants }
