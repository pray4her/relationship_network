"use client"

import { Menu as MenuPrimitive } from "@base-ui/react/menu"
import { ChevronRightIcon } from "lucide-react"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/dropdown-menu.css(showcase/dropdown-menu.html 为唯一标准)。
 *
 * 现有 API → 规格映射决策:
 * - Content sideOffset 默认 4 → 8(规格:open 态落在触发器下方 --space-2);面板宽度不再
 *   跟随触发器,改为规格 min-width --sidebar-width / max-width calc(--space-16 * 8)。
 * - SubContent 默认 side="right" align="center" sideOffset={-4}(规格:子菜单锚在触发行的
 *   垂直中点,向左重叠 --space-1 盖住父面板边缘,指针可平滑滑入)。
 * - Item/Label 的 inset(旧 shadcn 缩进)规格无对应物 → 映射为"文字与勾选/单选行的指示槽
 *   对齐"的组合值 ps = --space-2 + --icon-size-sm + --space-2,注释见下。
 * - 选中指示从旧 API 的右侧 CheckIcon 改为规格的前置保留指示槽(--icon-size-sm,checkbox
 *   为对勾、radio 为实心圆点,currentColor);visibility 携带选中态(keepMounted +
 *   data-unchecked:invisible),勾选与未勾选行始终对齐。
 * - 规格的 focus 环挂在 :focus(菜单焦点是编程式 roving,:focus-visible 永不匹配脚本
 *   focus);运行态 hover/键盘高亮用 base-ui 的 data-highlighted,同时提供
 *   data-[state=hover|focus-visible|active] 与 data-[state=opening|closing] 镜像,
 *   供预览页静态渲染(见 dev/ui/dropdown-menu/page.tsx)。
 * - 规格的 :has(.dropdown-menu__submenu) 去滚动帽规则不需要:base-ui 子菜单经 Portal
 *   渲染,不在父面板 DOM 内,不会被 overflow 裁剪。
 * - 触发器样式规格明确归 button.css 所有,本组件不加任何触发器样式;调用方用
 *   <DropdownMenuTrigger render={<Button variant="secondary">标签</Button>} 组合。
 *   注意:文字必须放在 render 元素内而不是 Trigger 的 children —— RSC 序列化后的
 *   render 元素 props 带 children: undefined 键,会在 base-ui mergeProps 时覆盖
 *   Trigger 自身的 children(SSR 出空按钮,dialog/alert-dialog 页亦有此坑)。
 */

/** 面板(根面板与子菜单面板共用)的表面配方:--popover + --border + --radius-md +
 *  --shadow-lift + --z-dropdown,--menu-max-height 滚动帽,--space-1 上下 gutter。 */
const menuPanelClasses =
  "z-[var(--z-dropdown)] flex max-h-[min(var(--menu-max-height),var(--available-height))] min-w-[var(--sidebar-width)] max-w-[calc(var(--space-16)*8)] flex-col overflow-x-hidden overflow-y-auto rounded-[var(--radius-md)] border-[length:var(--border-width)] border-border bg-popover py-[var(--space-1)] font-sans text-popover-foreground shadow-lift outline-none transition-[opacity,translate,visibility] duration-normal ease-standard focus-visible:shadow-[var(--shadow-lift),0_0_0_var(--ring-width)_var(--ring-focus)] data-closed:pointer-events-none data-closed:invisible data-closed:opacity-0 data-closed:duration-fast"

/** 根面板关闭时向触发器方向停靠 --space-1(垂直);子菜单面板水平停靠同一距离。 */
const menuPanelParkClasses = {
  root: "data-closed:-translate-y-[var(--space-1)] data-[state=opening]:-translate-y-[var(--space-0-5)] data-[state=opening]:opacity-[var(--opacity-disabled)] data-[state=closing]:opacity-[var(--opacity-disabled)]",
  sub: "data-closed:translate-x-[var(--space-1)] data-[state=opening]:translate-x-[var(--space-0-5)] data-[state=opening]:opacity-[var(--opacity-disabled)] data-[state=closing]:opacity-[var(--opacity-disabled)]",
} as const

/** 菜单项几何与状态(standard / icon+label / shortcut / checkbox / radio / 子菜单触发
 *  共用):36px min-height 楼层 = --control-height-sm + --space-1,--radius-xs 行圆角,
 *  --text-nav-link 字型;hover/高亮/focus 均为 --accent 填充,focus 叠加共享 ring。 */
const menuItemClasses =
  "group/dropdown-menu-item relative flex min-h-[calc(var(--control-height-sm)+var(--space-1))] w-full cursor-pointer items-center gap-[var(--space-2)] rounded-[var(--radius-xs)] py-[var(--space-1)] ps-[var(--space-2)] pe-[var(--space-3)] text-left font-sans text-[length:var(--text-nav-link)] leading-[var(--text-nav-link--line-height)] font-medium text-foreground outline-none select-none transition-[background-color,box-shadow,color] duration-fast ease-standard hover:bg-accent focus:bg-accent focus:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-highlighted:bg-accent data-[state=hover]:bg-accent data-[state=focus-visible]:bg-accent data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-inset:ps-[calc(var(--space-2)+var(--icon-size-sm)+var(--space-2))] data-disabled:pointer-events-none data-disabled:cursor-not-allowed data-disabled:opacity-[var(--opacity-disabled)] [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg]:[stroke-width:var(--stroke-width-icon)] [&_svg:not([class*='size-'])]:size-[var(--icon-size-sm)]"

/** destructive:项本身就是错误可见性 —— 静止 --destructive 文字,hover/active 走专用
 *  --destructive-hover / --destructive-active 交互 token,填充仍是共享 --accent。 */
const menuItemDestructiveClasses =
  "text-destructive hover:bg-accent hover:text-destructive-hover active:bg-accent active:text-destructive-active focus:bg-accent focus:text-destructive-hover data-highlighted:bg-accent data-highlighted:text-destructive-hover data-[state=hover]:bg-accent data-[state=hover]:text-destructive-hover data-[state=active]:text-destructive-active"

/** 规格 .dropdown-menu__check:--space-2 字形,stroke/fill 继承 currentColor。 */
const checkGlyph = (
  <svg aria-hidden="true" className="size-[var(--space-2)]" fill="none" viewBox="0 0 16 16">
    <path
      d="M3 8.5 6.5 12 13 4.5"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const dotGlyph = (
  <svg aria-hidden="true" className="size-[var(--space-2)]" fill="none" viewBox="0 0 16 16">
    <circle cx="8" cy="8" fill="currentColor" r="4" />
  </svg>
)

/** 规格 .dropdown-menu__indicator:前置保留槽,visibility 携带选中态(未勾选保留列宽)。 */
const indicatorSlotClasses = "flex size-[var(--icon-size-sm)] flex-none items-center justify-center"

function DropdownMenu({ ...props }: MenuPrimitive.Root.Props) {
  return <MenuPrimitive.Root data-slot="dropdown-menu" {...props} />
}

function DropdownMenuPortal({ ...props }: MenuPrimitive.Portal.Props) {
  return <MenuPrimitive.Portal data-slot="dropdown-menu-portal" {...props} />
}

function DropdownMenuTrigger({ ...props }: MenuPrimitive.Trigger.Props) {
  return <MenuPrimitive.Trigger data-slot="dropdown-menu-trigger" {...props} />
}

function DropdownMenuContent({
  align = "start",
  alignOffset = 0,
  side = "bottom",
  sideOffset = 8,
  className,
  ...props
}: MenuPrimitive.Popup.Props &
  Pick<MenuPrimitive.Positioner.Props, "align" | "alignOffset" | "side" | "sideOffset">) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner
        align={align}
        alignOffset={alignOffset}
        className="isolate z-[var(--z-dropdown)] outline-none"
        side={side}
        sideOffset={sideOffset}
      >
        <MenuPrimitive.Popup
          data-slot="dropdown-menu-content"
          className={cn(menuPanelClasses, menuPanelParkClasses.root, className)}
          {...props}
        />
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  )
}

function DropdownMenuGroup({ ...props }: MenuPrimitive.Group.Props) {
  return <MenuPrimitive.Group data-slot="dropdown-menu-group" {...props} />
}

function DropdownMenuLabel({
  className,
  inset,
  ...props
}: MenuPrimitive.GroupLabel.Props & {
  inset?: boolean
}) {
  return (
    <MenuPrimitive.GroupLabel
      data-inset={inset}
      data-slot="dropdown-menu-label"
      className={cn(
        "py-[var(--space-2)] ps-[var(--space-3)] pe-[var(--space-2)] font-sans text-[length:var(--text-caption-up)] leading-[var(--text-caption-up--line-height)] tracking-[var(--text-caption-up--letter-spacing)] font-medium uppercase text-caption-foreground data-inset:ps-[calc(var(--space-2)+var(--icon-size-sm)+var(--space-2))]",
        className,
      )}
      {...props}
    />
  )
}

function DropdownMenuItem({
  className,
  inset,
  variant = "default",
  ...props
}: MenuPrimitive.Item.Props & {
  inset?: boolean
  variant?: "default" | "destructive"
}) {
  return (
    <MenuPrimitive.Item
      data-inset={inset}
      data-slot="dropdown-menu-item"
      data-variant={variant}
      className={cn(
        menuItemClasses,
        variant === "destructive" && menuItemDestructiveClasses,
        className,
      )}
      {...props}
    />
  )
}

function DropdownMenuSub({ ...props }: MenuPrimitive.SubmenuRoot.Props) {
  return <MenuPrimitive.SubmenuRoot data-slot="dropdown-menu-sub" {...props} />
}

function DropdownMenuSubTrigger({
  className,
  inset,
  children,
  ...props
}: MenuPrimitive.SubmenuTrigger.Props & {
  inset?: boolean
}) {
  return (
    <MenuPrimitive.SubmenuTrigger
      data-inset={inset}
      data-slot="dropdown-menu-sub-trigger"
      className={cn(
        menuItemClasses,
        // 规格:展开的分支保持 --accent 行高亮;hover 再深一层 --surface-cream-pressed
        // (accordion-open hover 配方)。
        "data-open:bg-accent data-popup-open:bg-accent hover:data-open:bg-[var(--surface-cream-pressed)] hover:data-popup-open:bg-[var(--surface-cream-pressed)]",
        className,
      )}
      {...props}
    >
      {children}
      <ChevronRightIcon
        data-slot="dropdown-menu-sub-chevron"
        className="ms-auto text-muted-foreground transition-transform duration-normal ease-standard group-data-open/dropdown-menu-item:rotate-180 group-data-popup-open/dropdown-menu-item:rotate-180"
      />
    </MenuPrimitive.SubmenuTrigger>
  )
}

function DropdownMenuSubContent({
  align = "center",
  alignOffset = 0,
  side = "right",
  sideOffset = -4,
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuContent>) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner
        align={align}
        alignOffset={alignOffset}
        className="isolate z-[var(--z-dropdown)] outline-none"
        side={side}
        sideOffset={sideOffset}
      >
        <MenuPrimitive.Popup
          data-slot="dropdown-menu-sub-content"
          className={cn(menuPanelClasses, menuPanelParkClasses.sub, className)}
          {...props}
        />
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  )
}

function DropdownMenuCheckboxItem({
  className,
  children,
  checked,
  inset,
  ...props
}: MenuPrimitive.CheckboxItem.Props & {
  inset?: boolean
}) {
  return (
    <MenuPrimitive.CheckboxItem
      checked={checked}
      data-inset={inset}
      data-slot="dropdown-menu-checkbox-item"
      className={cn(menuItemClasses, className)}
      {...props}
    >
      <span className={indicatorSlotClasses} data-slot="dropdown-menu-item-indicator">
        <MenuPrimitive.CheckboxItemIndicator keepMounted className="data-unchecked:invisible">
          {checkGlyph}
        </MenuPrimitive.CheckboxItemIndicator>
      </span>
      {children}
    </MenuPrimitive.CheckboxItem>
  )
}

function DropdownMenuRadioGroup({ ...props }: MenuPrimitive.RadioGroup.Props) {
  return <MenuPrimitive.RadioGroup data-slot="dropdown-menu-radio-group" {...props} />
}

function DropdownMenuRadioItem({
  className,
  children,
  inset,
  ...props
}: MenuPrimitive.RadioItem.Props & {
  inset?: boolean
}) {
  return (
    <MenuPrimitive.RadioItem
      data-inset={inset}
      data-slot="dropdown-menu-radio-item"
      className={cn(menuItemClasses, className)}
      {...props}
    >
      <span className={indicatorSlotClasses} data-slot="dropdown-menu-item-indicator">
        <MenuPrimitive.RadioItemIndicator keepMounted className="data-unchecked:invisible">
          {dotGlyph}
        </MenuPrimitive.RadioItemIndicator>
      </span>
      {children}
    </MenuPrimitive.RadioItem>
  )
}

function DropdownMenuSeparator({ className, ...props }: MenuPrimitive.Separator.Props) {
  return (
    <MenuPrimitive.Separator
      data-slot="dropdown-menu-separator"
      className={cn(
        "my-[var(--space-1)] h-0 border-b-[length:var(--border-width)] border-border-soft",
        className,
      )}
      {...props}
    />
  )
}

function DropdownMenuShortcut({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="dropdown-menu-shortcut"
      className={cn(
        "ms-auto font-mono text-[length:var(--text-caption-up)] leading-[var(--text-caption-up--line-height)] font-normal text-caption-foreground",
        className,
      )}
      {...props}
    />
  )
}

export {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
}
