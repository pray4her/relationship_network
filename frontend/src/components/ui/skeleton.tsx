import { cva, type VariantProps } from "class-variance-authority"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/skeleton.css(showcase/skeleton.html 为唯一标准)。
 *
 * API 映射:
 * - variant(新增):规格的三个形状修饰符 —— rectangle(默认,控件高度块 · --radius-md)、
 *   text(body-md 行盒 · --radius-sm)、circle(Avatar 尺度 --avatar-size-md 圆盘 · --radius-full)。
 * - 尺寸不设阶梯(规格明确 "no encoded size ladder"):规格的 --_w / --_h / --_r 内联别名
 *   在 Tailwind 下等价于调用方用镜像内容的 token 写 w-[...] / h-[...] / rounded-[...] 任意值,
 *   冲突经 tailwind-merge 消解;表面覆盖同理(bg-(--surface-cream-strong) 对应 --_bg)。
 * - 规格的 .skeleton--static / .skeleton--reduced-motion 预览态镜像为
 *   data-[state=static] / data-[state=reduced-motion];真实 prefers-reduced-motion
 *   由 motion-reduce 变体承担(扫带移除,静态奶油块仍是占位符)。
 * - 动效:--skeleton-animation-duration(= --duration-loading)· --skeleton-animation-easing
 *   (= --ease-standard);@keyframes 无法经工具类注册,由下方 React 19 提升的
 *   <style precedence> 内联定义(同内容跨实例去重),值仍全部引用 token。
 * - a11y 合同:每块 skeleton 默认 aria-hidden;加载态由外层区域 aria-busy + aria-label 表达。
 */
const skeletonVariants = cva(
  "relative w-full overflow-hidden rounded-[var(--skeleton-radius-rectangle)] bg-(--skeleton-surface) after:absolute after:inset-y-0 after:w-(--skeleton-highlight-size) after:animate-[skeleton-sweep_var(--skeleton-animation-duration)_var(--skeleton-animation-easing)_infinite] after:bg-[linear-gradient(90deg,transparent,var(--skeleton-highlight),transparent)] after:opacity-(--skeleton-highlight-opacity) after:content-[''] motion-reduce:after:hidden motion-reduce:after:animate-none data-[state=reduced-motion]:after:hidden data-[state=reduced-motion]:after:animate-none data-[state=static]:after:hidden data-[state=static]:after:animate-none",
  {
    variants: {
      variant: {
        rectangle: "h-[var(--space-8)]",
        text: "h-[calc(var(--text-body-md)*var(--text-body-md--line-height))] rounded-[var(--skeleton-radius-text)]",
        circle: "size-[var(--avatar-size-md)] shrink-0 rounded-[var(--skeleton-radius-circle)]",
      },
    },
    defaultVariants: {
      variant: "rectangle",
    },
  },
)

/** 规格 @keyframes skeleton-sweep:扫带从轨道外左侧行至 100%,首尾偏移复用扫带宽度 token。 */
const skeletonSweepKeyframes =
  "@keyframes skeleton-sweep{from{inset-inline-start:calc(-1 * var(--skeleton-highlight-size))}to{inset-inline-start:100%}}"

type SkeletonProps = React.ComponentProps<"div"> & VariantProps<typeof skeletonVariants>

function Skeleton({ className, variant, ...props }: SkeletonProps) {
  return (
    <>
      <style precedence="rn-skeleton">{skeletonSweepKeyframes}</style>
      <div
        aria-hidden="true"
        className={cn(skeletonVariants({ variant }), className)}
        data-slot="skeleton"
        {...props}
      />
    </>
  )
}

export { Skeleton, skeletonVariants }
