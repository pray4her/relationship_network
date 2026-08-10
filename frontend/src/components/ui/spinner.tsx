import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/spinner.css(showcase 为唯一标准)。
 * 组合合同(markup contract):
 *  - 仅 ring:wrapper 携带 role="status" + aria-label(默认 "Loading",可经 props 覆盖);
 *    旁有文字已说明状态时可传 aria-hidden 视为装饰(此时 role/aria-label 自动省略)。
 *  - ring + label:label prop 渲染可见 .spinner__label,wrapper 为 role="status"
 *    隐式 polite live region,可见文本即可访问名;ring 恒 aria-hidden。
 *  - Button 内联:作为图标位子节点传入并 aria-hidden,Button 文案即可访问名;
 *    填充按钮用 inverse,quiet 按钮用 default。
 * 尺寸 xs/sm/md/lg 走 icon-size 阶梯(12/16/18/24),描边 xs–md 为 --space-0-5,
 * lg 升一档至 --space-0-75;旋转 --duration-slow linear infinite。
 * reduced-motion 经 motion-reduce 冻结为静态弧;预览页用 data-state="reduced" 静态镜像。
 *
 * API 迁移说明:旧实现为 lucide Loader2Icon svg,无 variant/size;
 * 旧默认视觉(size-4 = 16px)对应新 size="sm",规格默认值为 md,此处以规格为准。
 */
const spinnerRingVariants = cva(
  "shrink-0 animate-spin rounded-full border-[length:var(--space-0-5)] border-solid [animation-duration:var(--duration-slow)] [animation-timing-function:linear] motion-reduce:animate-none data-[state=reduced]:animate-none",
  {
    variants: {
      variant: {
        default: "border-border border-t-foreground",
        primary: "border-[color:var(--primary-disabled)] border-t-primary",
        inverse: "border-[color:var(--surface-dark-elevated)] border-t-on-dark",
      },
      size: {
        xs: "size-[var(--icon-size-xs)]",
        sm: "size-[var(--icon-size-sm)]",
        md: "size-[var(--icon-size-md)]",
        lg: "size-[var(--icon-size-lg)] border-[length:var(--space-0-75)]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
)

type SpinnerProps = React.ComponentProps<"span"> &
  VariantProps<typeof spinnerRingVariants> & {
    /** 可见加载文本:出现时即可访问名,wrapper 为 live region,ring 保持 aria-hidden。 */
    label?: string
  }

function Spinner({ className, variant = "default", size = "md", label, ...props }: SpinnerProps) {
  const decorative = props["aria-hidden"] === true || props["aria-hidden"] === "true"
  // 装饰态省略 role/aria-label;可见 label 存在时即可访问名,不再加 aria-label。
  // 经对象展开挂载:role/aria-label 是否出现取决于运行时状态。
  const statusProps: Pick<SpinnerProps, "role" | "aria-label"> = decorative
    ? {}
    : { role: "status", "aria-label": label ? undefined : "Loading" }
  return (
    <span
      className={cn("inline-flex items-center gap-[var(--space-2)]", className)}
      data-slot="spinner"
      {...statusProps}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(spinnerRingVariants({ variant, size }))}
        data-slot="spinner-ring"
      />
      {label && (
        <span
          className={cn(
            "font-sans text-sm font-medium",
            variant === "inverse" ? "text-on-dark-soft" : "text-muted-foreground",
          )}
          data-slot="spinner-label"
        >
          {label}
        </span>
      )}
    </span>
  )
}

export { Spinner, spinnerRingVariants }
