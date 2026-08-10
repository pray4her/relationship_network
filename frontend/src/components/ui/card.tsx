import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/card.css(showcase 为唯一标准)。
 * 可组合的表面容器:各部件可选、顺序自由,variant 是表面配方而非内容类型。
 *
 * 交互契约(规格定义两种模式,不可混用):
 *   A) 整卡可交互:根节点本身是 <a>/<button>(经 render prop 传入)+ interactive。
 *      内容必须非交互;hover/active/focus-visible/disabled 同时挂伪类与
 *      data-[state=*] 镜像,预览页可静态渲染。
 *   B) 卡片带操作:根节点 inert(默认 <div>),交互只存在于 CardActions 的子元素。
 *
 * API 映射:规格只定义一种 padding(--space-8);size="sm" 无规格对应物,
 * 映射到最近的较小 spacing 档 --space-6。规格有而旧 API 没有的 variant
 * (outlined/elevated/selected)、interactive 状态、CardMedia/CardActions
 * 部件按规格 markup 合同新增,均为可选。
 */
const cardVariants = cva(
  "group/card flex flex-col gap-[var(--space-4)] rounded-[var(--radius-lg)] border-[length:var(--border-width)] bg-clip-padding p-[var(--space-8)] text-start font-sans text-foreground no-underline outline-none data-[size=sm]:p-[var(--space-6)]",
  {
    variants: {
      variant: {
        default: "border-transparent bg-card shadow-none",
        outlined: "border-border bg-background shadow-none",
        elevated: "border-transparent bg-background shadow-subtle",
        selected: "border-[var(--selected-border)] bg-[var(--selected-bg)] shadow-none",
      },
      interactive: {
        false: "",
        true: "cursor-pointer transition-[box-shadow,border-color,background-color] duration-normal ease-standard motion-reduce:transition-none active:shadow-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=active]:shadow-none data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=disabled]:pointer-events-none data-[state=disabled]:cursor-not-allowed data-[state=disabled]:opacity-[var(--opacity-disabled)] aria-disabled:pointer-events-none aria-disabled:cursor-not-allowed aria-disabled:opacity-[var(--opacity-disabled)]",
      },
    },
    compoundVariants: [
      {
        variant: "default",
        interactive: true,
        class: "hover:shadow-subtle data-[state=hover]:shadow-subtle",
      },
      {
        variant: "outlined",
        interactive: true,
        class: "hover:shadow-subtle data-[state=hover]:shadow-subtle",
      },
      {
        variant: "selected",
        interactive: true,
        class: "hover:shadow-subtle data-[state=hover]:shadow-subtle",
      },
      {
        variant: "elevated",
        interactive: true,
        class: "hover:shadow-lift data-[state=hover]:shadow-lift",
      },
    ],
    defaultVariants: {
      variant: "default",
      interactive: false,
    },
  },
)

type CardProps = useRender.ComponentProps<"div"> &
  VariantProps<typeof cardVariants> & {
    /** 规格未定义紧凑尺寸;映射到最近的较小 spacing 档(--space-6)。 */
    size?: "default" | "sm"
    /** 整卡可交互(pattern A)且根为 <button> 时的原生禁用;透传到 render 的根元素。 */
    disabled?: boolean | undefined
  }

function Card({
  className,
  variant = "default",
  interactive = false,
  size = "default",
  render,
  ...props
}: CardProps) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(cardVariants({ variant, interactive }), className),
      },
      props,
    ),
    render,
    state: {
      slot: "card",
      variant,
      interactive,
      size,
    },
  })
}

/** 规格 card__media:必须是根节点的第一个子元素,负 margin 复用 padding token 贴边。 */
function CardMedia({ className, ...props }: useRender.ComponentProps<"figure">) {
  return useRender({
    defaultTagName: "figure",
    props: mergeProps<"figure">(
      {
        className: cn(
          "-mx-[var(--space-8)] -mt-[var(--space-8)] overflow-hidden rounded-t-[var(--radius-lg)] group-data-[size=sm]/card:-mx-[var(--space-6)] group-data-[size=sm]/card:-mt-[var(--space-6)] [&_img]:block [&_img]:h-auto [&_img]:w-full",
          className,
        ),
      },
      props,
    ),
    state: { slot: "card-media" },
  })
}

function CardHeader({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn("flex items-center gap-[var(--space-3)]", className),
      },
      props,
    ),
    state: { slot: "card-header" },
  })
}

function CardTitle({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(
          "m-0 font-sans text-[length:var(--text-title-md)] leading-[var(--text-title-md--line-height)] font-medium text-foreground",
          className,
        ),
      },
      props,
    ),
    state: { slot: "card-title" },
  })
}

function CardDescription({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(
          "m-0 text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] text-muted-foreground",
          className,
        ),
      },
      props,
    ),
    state: { slot: "card-description" },
  })
}

/** 旧 API 保留:规格中等价物是 header 行尾的 action 位,经 ml-auto 靠右对齐。 */
function CardAction({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn("ml-auto self-start", className),
      },
      props,
    ),
    state: { slot: "card-action" },
  })
}

function CardContent({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(
          "text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)] text-foreground-body [&>:first-child]:mt-0 [&>:last-child]:mb-0",
          className,
        ),
      },
      props,
    ),
    state: { slot: "card-content" },
  })
}

function CardFooter({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(
          "border-border-soft border-t-[length:var(--border-width)] pt-[var(--space-4)]",
          className,
        ),
      },
      props,
    ),
    state: { slot: "card-footer" },
  })
}

/** 规格 card__actions:组合真实 Button/Link 子元素,不重新设计样式。 */
function CardActions({ className, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn("flex flex-wrap items-center gap-[var(--space-3)]", className),
      },
      props,
    ),
    state: { slot: "card-actions" },
  })
}

export {
  Card,
  CardAction,
  CardActions,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardMedia,
  CardTitle,
  cardVariants,
}
