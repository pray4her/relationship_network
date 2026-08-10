"use client"

import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/form-field.css 的 .field__label / .field__required 段落
 * (showcase/form-field.html 为唯一标准)。
 * 规格中 label 没有 variant/size,API 保持原生 <label> props 直通,现有调用处不受影响。
 *
 * 状态协调:规格里 label 的状态由父级 .field 通过 :has() 读取子控件真实状态推导,
 * 单独的 Label 组件无法跨层级 :has(),因此:
 *   - disabled 保留 peer-disabled(同级前置控件)与 group-data-[disabled=true]
 *     (Field 的 group/field)两条真实链路,透明度用 --opacity-disabled;
 *   - focus-visible(子控件聚焦 → --foreground)、readonly(→ --muted-foreground)、
 *     error(→ --destructive)提供 data-[state=*] 镜像,预览页可静态渲染。
 */
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex cursor-pointer items-center gap-[var(--space-2)] font-sans text-caption font-medium text-foreground-strong transition-colors duration-fast ease-standard select-none",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-[var(--opacity-disabled)]",
        "group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:cursor-not-allowed group-data-[disabled=true]:opacity-[var(--opacity-disabled)]",
        "data-[state=focus-visible]:text-foreground",
        "data-[state=disabled]:cursor-not-allowed data-[state=disabled]:opacity-[var(--opacity-disabled)]",
        "data-[state=readonly]:text-muted-foreground",
        "data-[state=error]:text-destructive",
        className,
      )}
      {...props}
    />
  )
}

/**
 * 必填标记(.field__required):与 label 同字号,颜色 --destructive;
 * 纯视觉、aria-hidden —— 语义由控件自身的 required 属性承担。
 */
function LabelRequired({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden="true"
      data-slot="label-required"
      className={cn("text-destructive", className)}
      {...props}
    />
  )
}

export { Label, LabelRequired }
