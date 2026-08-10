"use client"

import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/tabs.css(showcase 为唯一标准)。
 * hover/active/focus-visible 同时挂伪类与 data-[state=*] 镜像,预览页可静态渲染;
 * 选中态只认 aria-selected / data-active(规格:selection is styled from
 * aria-selected="true",never a parallel class)。
 * API 映射(规格无同名概念,映射到最近规格):
 *   variant "default"(旧药丸容器)→ 规格 contained("Category tabs" 配方);
 *   variant "line"(旧下划线)→ 规格 underline(quiet rail + coral 指示器,规格的默认 variant);
 *   size 为新增可选 prop:sm/lg 对应规格 --sm/--lg 修饰(共享控件阶梯),缺省 = md。
 * variant/size 挂在 list 的 data 属性上,trigger 经 group-data-* 选择器读取(沿用旧模式)。
 */
const tabsListVariants = cva(
  // 规格 .tabs__list:横向可滚动(flex none 由 tab 承担),--ring-width 的负 margin
  // 补偿为 focus 环留出不被裁剪的空间。
  "group/tabs-list -my-[var(--ring-width)] flex min-w-0 overflow-x-auto py-[var(--ring-width)]",
  {
    variants: {
      variant: {
        default: "gap-[var(--space-1)]",
        line: "gap-[var(--space-2)] border-border-soft border-b-[length:var(--border-width)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

function Tabs({ className, orientation = "horizontal", ...props }: TabsPrimitive.Root.Props) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      className={cn("group/tabs flex min-w-0 data-[orientation=horizontal]:flex-col", className)}
      {...props}
    />
  )
}

type TabsListProps = TabsPrimitive.List.Props &
  VariantProps<typeof tabsListVariants> & {
    /** 规格的尺寸修饰:sm/lg 走共享控件阶梯(--control-height-sm/--control-height-lg),缺省 md。 */
    size?: "sm" | "default" | "lg"
  }

function TabsList({ className, variant = "default", size = "default", ...props }: TabsListProps) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      data-size={size}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn(
        // 共享 tab chrome:高度/排版/inline padding/gap/动效/disabled/focus 环;
        // 图标 --icon-size-sm + --stroke-width-icon,badge 组合只防压缩(规格:composed unmodified)。
        "relative inline-flex h-[var(--control-height)] flex-none cursor-pointer select-none items-center justify-center gap-[var(--space-2)] px-[var(--tab-padding-inline)] font-sans text-[length:var(--text-nav-link)] leading-[var(--text-nav-link--line-height)] font-medium whitespace-nowrap text-muted-foreground transition-[color,background-color,box-shadow] duration-fast ease-standard outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-[var(--opacity-disabled)] data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] motion-reduce:transition-none [&_[data-slot=badge]]:flex-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)] [&_svg_path]:[stroke-width:var(--stroke-width-icon)]",
        // underline(= variant line):负 margin 把指示器贴到 rail;指示器是 inset 阴影,
        // focus 环可叠加而不移位;选中 + focus 时两层阴影叠加(规格的更高优先级规则)。
        "group-data-[variant=line]/tabs-list:-mb-[var(--ring-width)] group-data-[variant=line]/tabs-list:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_transparent] group-data-[variant=line]/tabs-list:hover:text-[color:var(--muted-foreground-hover)] group-data-[variant=line]/tabs-list:active:text-[color:var(--muted-foreground-active)] group-data-[variant=line]/tabs-list:focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] group-data-[variant=line]/tabs-list:data-[state=hover]:text-[color:var(--muted-foreground-hover)] group-data-[variant=line]/tabs-list:data-[state=active]:text-[color:var(--muted-foreground-active)] group-data-[variant=line]/tabs-list:data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] group-data-[variant=line]/tabs-list:data-active:text-foreground group-data-[variant=line]/tabs-list:data-active:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--primary)] group-data-[variant=line]/tabs-list:aria-selected:text-foreground group-data-[variant=line]/tabs-list:aria-selected:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--primary)]",
        "group-data-[variant=line]/tabs-list:aria-selected:focus-visible:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--primary),0_0_0_var(--ring-width)_var(--ring-focus)] group-data-[variant=line]/tabs-list:aria-selected:data-[state=focus-visible]:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--primary),0_0_0_var(--ring-width)_var(--ring-focus)] group-data-[variant=line]/tabs-list:data-active:data-[state=focus-visible]:shadow-[inset_0_calc(-1*var(--border-width-strong))_0_var(--primary),0_0_0_var(--ring-width)_var(--ring-focus)]",
        // contained(= variant default):透明静置,--accent hover("hover/tab-active bg"),
        // --surface-cream-strong pressed,--selected-bg 选中(语义选中面,比 hover 深一档)。
        "group-data-[variant=default]/tabs-list:rounded-[var(--radius-md)] group-data-[variant=default]/tabs-list:hover:bg-accent group-data-[variant=default]/tabs-list:hover:text-accent-foreground group-data-[variant=default]/tabs-list:active:bg-surface-cream-strong group-data-[variant=default]/tabs-list:data-[state=hover]:bg-accent group-data-[variant=default]/tabs-list:data-[state=hover]:text-accent-foreground group-data-[variant=default]/tabs-list:data-[state=active]:bg-surface-cream-strong group-data-[variant=default]/tabs-list:data-active:bg-[var(--selected-bg)] group-data-[variant=default]/tabs-list:data-active:text-foreground group-data-[variant=default]/tabs-list:aria-selected:bg-[var(--selected-bg)] group-data-[variant=default]/tabs-list:aria-selected:text-foreground",
        // sizes(规格 --sm/--lg 修饰):高度/inline padding/字号阶梯,lg 图标升至 --icon-size-md。
        "group-data-[size=sm]/tabs-list:h-[var(--control-height-sm)] group-data-[size=sm]/tabs-list:px-[var(--space-3)] group-data-[size=sm]/tabs-list:text-[length:var(--text-caption)] group-data-[size=sm]/tabs-list:leading-[var(--text-caption--line-height)]",
        "group-data-[size=lg]/tabs-list:h-[var(--control-height-lg)] group-data-[size=lg]/tabs-list:px-[var(--space-6)] group-data-[size=lg]/tabs-list:text-[length:var(--text-title-sm)] group-data-[size=lg]/tabs-list:leading-[var(--text-title-sm--line-height)] group-data-[size=lg]/tabs-list:[&_svg:not([class*='size-'])]:size-[var(--icon-size-md)]",
        className,
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn(
        // 规格 .tabs__panel:padding-block-start --space-4;panel 可聚焦(tabindex=0),
        // focus 环用共享 ring 配方 + --radius-md。
        "flex-1 rounded-[var(--radius-md)] pt-[var(--space-4)] outline-none focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)]",
        className,
      )}
      {...props}
    />
  )
}

export { Tabs, TabsContent, TabsList, TabsTrigger, tabsListVariants }
