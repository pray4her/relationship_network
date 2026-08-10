"use client"

import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/table.css(showcase 为唯一标准)。
 * 行状态同时挂伪类与 data-[state=hover|selected|focus-visible|disabled] 镜像,
 * 预览页可静态渲染 hover/selected/focus/disabled 态(先例:ui/button.tsx)。
 *
 * API 映射说明:
 * - 行状态镜像规格 .is-* 类:.is-hover → data-state="hover"、.is-selected →
 *   data-state="selected"、.is-focus-visible/.is-focus → data-state="focus-visible"/"focus"、
 *   .is-disabled → data-state="disabled" + aria-disabled(markup 合同)。
 * - 规格有而旧 API 没有的解剖件按 markup 合同补为可选组件:TableSortButton /
 *   TableSortIcon(.table__sort + 方向箭头,方向由 <th aria-sort> 驱动)、
 *   TableCheckbox(.table__checkbox,原生 accent-color 对齐 checkbox.css 的 --primary
 *   填充规格,ui/checkbox.tsx 落地后可换组合)、
 *   TableActions(.table__actions,行内 icon-button 容器)。
 * - 规格有而旧 API 没有的单元格修饰补为可选 prop:TableCell 的 strong
 *   (.table__cell--strong)与 numeric(.table__cell--number)。
 * - 规格缺口:caption 无对应规则,映射到 spec footer 的 caption 文本配方
 *   (--text-caption + --caption-foreground),保持 caption-bottom 布局不变。
 */

/**
 * 规格 .table-wrap:hairline 容器 + radius-lg + 横向滚动轨道(overflow-y: visible,
 * 保留页面自加 sticky header 的可能)。表格 min-width 永远由页面上下文决定,组件不设。
 */
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      className="w-full overflow-x-auto overflow-y-visible rounded-[var(--radius-lg)] border border-border bg-background"
      data-slot="table-container"
    >
      <table
        className={cn(
          "w-full caption-bottom border-collapse text-start font-sans text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)] text-foreground-body",
          className,
        )}
        data-slot="table"
        {...props}
      />
    </div>
  )
}

/** 规格:表头行不继承 body 的行分隔线,hairline(--border)画在 th 底部。 */
function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead className={cn("[&_tr]:border-b-0", className)} data-slot="table-header" {...props} />
  )
}

/** 规格:末行之下不画分隔线(one line under the header, none under the final row)。 */
function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      className={cn("[&_tr:last-child]:border-b-0", className)}
      data-slot="table-body"
      {...props}
    />
  )
}

/**
 * 规格 tfoot:镜像表头 band —— surface-soft 底、顶部 --border hairline、caption 文本
 * 配方(--text-caption / medium / --caption-foreground);footer 行不参与行态(无 hover、
 * 无分隔线、无 selection/focus 阴影)。
 */
function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      className={cn(
        "border-border border-t bg-surface-soft font-medium text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-caption-foreground",
        "[&_tr]:border-b-0 [&_tr]:bg-transparent [&_tr]:shadow-none [&_tr]:hover:bg-transparent",
        className,
      )}
      data-slot="table-footer"
      {...props}
    />
  )
}

/**
 * 规格行态(伪类 + data-state 镜像,hover 不覆盖 selected/disabled):
 * default bg --background;hover bg --surface-soft;selected --selected-bg 填充 +
 * --border-width-strong 内嵌 leading edge(--selected-border);focus-within 内嵌
 * --ring-focus 环(与 selected edge 双 inset 阴影叠加,互不冲突);disabled
 * opacity --opacity-disabled + cursor not-allowed。
 * 镜像选择器用 [data-state~=x] 词匹配,单属性可组合多态(如 "selected focus-visible")。
 */
function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      className={cn(
        "border-border-soft border-b bg-background transition-[background-color] duration-fast ease-standard motion-reduce:transition-none",
        "hover:not-data-[state~=selected]:not-data-[state~=disabled]:bg-surface-soft",
        "data-[state~=hover]:not-data-[state~=selected]:not-data-[state~=disabled]:bg-surface-soft",
        "data-[state~=selected]:bg-[color:var(--selected-bg)] data-[state~=selected]:shadow-[inset_var(--border-width-strong)_0_0_var(--selected-border)]",
        "focus-within:shadow-[inset_0_0_0_var(--ring-width)_var(--ring-focus)]",
        "data-[state~=focus-visible]:shadow-[inset_0_0_0_var(--ring-width)_var(--ring-focus)]",
        "data-[state~=focus]:shadow-[inset_0_0_0_var(--ring-width)_var(--ring-focus)]",
        "focus-within:data-[state~=selected]:shadow-[inset_var(--border-width-strong)_0_0_var(--selected-border),inset_0_0_0_var(--ring-width)_var(--ring-focus)]",
        "data-[state~=focus-visible]:data-[state~=selected]:shadow-[inset_var(--border-width-strong)_0_0_var(--selected-border),inset_0_0_0_var(--ring-width)_var(--ring-focus)]",
        "data-[state~=focus]:data-[state~=selected]:shadow-[inset_var(--border-width-strong)_0_0_var(--selected-border),inset_0_0_0_var(--ring-width)_var(--ring-focus)]",
        "data-[state~=disabled]:cursor-not-allowed data-[state~=disabled]:opacity-[var(--opacity-disabled)] data-[state~=disabled]:[&>td]:cursor-not-allowed",
        className,
      )}
      data-slot="table-row"
      {...props}
    />
  )
}

/**
 * 规格 thead th:--surface-soft band、底部 --border hairline、padding block --space-4 /
 * inline --space-6、caption-up 全配方(--text-caption-up + line-height + letter-spacing +
 * uppercase)、--muted-foreground、medium weight。
 */
function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      className={cn(
        "group/th border-border border-b bg-surface-soft px-[var(--space-6)] py-[var(--space-4)] text-left align-middle font-medium text-[length:var(--text-caption-up)] text-muted-foreground uppercase leading-[var(--text-caption-up--line-height)] tracking-[var(--text-caption-up--letter-spacing)]",
        className,
      )}
      data-slot="table-head"
      {...props}
    />
  )
}

type TableCellProps = React.ComponentProps<"td"> & {
  /** 规格 .table__cell--strong:--foreground + --font-weight-medium(强调单元格)。 */
  strong?: boolean
  /** 规格 .table__cell--number:右对齐数字列。 */
  numeric?: boolean
}

/** 规格 tbody td:padding block --space-3 / inline --space-6。 */
function TableCell({ className, strong, numeric, ...props }: TableCellProps) {
  return (
    <td
      className={cn(
        "px-[var(--space-6)] py-[var(--space-3)] align-middle",
        strong && "font-medium text-foreground",
        numeric && "text-end",
        className,
      )}
      data-slot="table-cell"
      {...props}
    />
  )
}

/**
 * 规格缺口:caption 无独立规则,映射 footer 的 caption 文本配方
 * (--text-caption + --caption-foreground),保留 caption-bottom 布局合同。
 */
function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      className={cn(
        "mt-[var(--space-4)] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-caption-foreground",
        className,
      )}
      data-slot="table-caption"
      {...props}
    />
  )
}

/**
 * 规格 .table__sort:<th aria-sort> 内的原生 <button>,继承 th 的 caption-up 排版与
 * --muted-foreground;hover → --muted-foreground-hover;focus-visible → 共享 ring 配方;
 * sorted 列(th[aria-sort=ascending|descending])读作 --foreground ink。
 */
function TableSortButton({ className, type = "button", ...props }: React.ComponentProps<"button">) {
  return (
    <button
      className={cn(
        "group/sort inline-flex cursor-pointer items-center gap-[var(--space-1)] text-inherit transition-colors duration-fast ease-standard motion-reduce:transition-none",
        "hover:text-[color:var(--muted-foreground-hover)] data-[state=hover]:text-[color:var(--muted-foreground-hover)]",
        "focus-visible:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] focus-visible:outline-none",
        "data-[state=focus-visible]:shadow-[0_0_0_var(--ring-width)_var(--ring-focus)] data-[state=focus-visible]:outline-none",
        "group-aria-[sort=ascending]/th:text-foreground group-aria-[sort=descending]/th:text-foreground",
        className,
      )}
      data-slot="table-sort"
      type={type}
      {...props}
    />
  )
}

const sortIconClass =
  "size-[var(--icon-size-xs)] shrink-0 text-caption-foreground [stroke-width:var(--stroke-width-icon)] group-hover/sort:text-foreground group-aria-[sort=ascending]/th:text-current group-aria-[sort=descending]/th:text-current"

/**
 * 规格 .table__sort-icon:--icon-size-xs、stroke --stroke-width-icon;unsorted 时
 * --caption-foreground 静置提示,hover 抬升至 --foreground,sorted 转 currentColor。
 * 方向交换由 <th aria-sort> 驱动:ascending 隐藏降序箭头,descending 隐藏升序箭头。
 */
function TableSortIcon() {
  return (
    <>
      <svg
        aria-hidden="true"
        className={cn(sortIconClass, "group-aria-[sort=descending]/th:hidden")}
        data-slot="table-sort-icon-asc"
        fill="none"
        viewBox="0 0 24 24"
      >
        <path
          d="M12 19V5m-6 6 6-6 6 6"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <svg
        aria-hidden="true"
        className={cn(sortIconClass, "group-aria-[sort=ascending]/th:hidden")}
        data-slot="table-sort-icon-desc"
        fill="none"
        viewBox="0 0 24 24"
      >
        <path
          d="M12 5v14m6-6-6 6-6-6"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </>
  )
}

/**
 * 规格 .table__checkbox:display block + margin 0。视觉规格来自 checkbox.css
 * (checked/indeterminate → --primary 填充):ui/checkbox.tsx 落地前用原生
 * accent-color(--primary)+ --checkbox-size-md 尺寸对齐规格;indeterminate
 * 由控制器经 indeterminate prop 透传设置(el.indeterminate 只能由 JS 设置)。
 */
type TableCheckboxProps = Omit<React.ComponentProps<"input">, "type"> & {
  /** select-all 半选态:对应原生 el.indeterminate,只能由 JS 设置。 */
  indeterminate?: boolean
}

function TableCheckbox({ className, indeterminate, ...props }: TableCheckboxProps) {
  return (
    <input
      className={cn("block size-[var(--checkbox-size-md)] accent-[var(--primary)]", className)}
      data-slot="table-checkbox"
      ref={(el) => {
        if (el) {
          el.indeterminate = indeterminate ?? false
        }
      }}
      type="checkbox"
      {...props}
    />
  )
}

/** 规格 .table__actions:行操作容器,flex row、gap --space-1(按钮样式来自 icon-button 规格)。 */
function TableActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex items-center gap-[var(--space-1)]", className)}
      data-slot="table-actions"
      {...props}
    />
  )
}

export {
  Table,
  TableActions,
  TableBody,
  TableCaption,
  TableCell,
  TableCheckbox,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
  TableSortButton,
  TableSortIcon,
}
