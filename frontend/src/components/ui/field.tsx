"use client"

import { cva, type VariantProps } from "class-variance-authority"
import { useMemo } from "react"

import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

/**
 * 视觉规格:frontend/src/styles/form-field.css(showcase/form-field.html 为唯一标准)。
 * 状态协调:disabled/readonly/focus 经 :has() 读取控件真实状态(规格合同,什么都不复制),
 * 另挂 data-[state=focused|disabled|readonly|error] 镜像,预览页可静态渲染。
 * 焦点环归控件自己(--ring-width / --ring-focus),field 只提亮 label。
 *
 * API → 规格映射(规格无对应物的就近映射,不改变布局语义):
 * - Field orientation: vertical → .field(grid,gap --space-2);
 *   horizontal/responsive 规格未覆盖,保留旧布局,间距换 --space-4(header row 同款间距)。
 * - FieldLabel 不再套 ui/label 基元(其旧刻度 text-sm 会与 text-caption 冲突),
 *   直接按 .field__label 实现:font-sans / text-caption / font-medium / --foreground-strong。
 * - FieldSet / FieldLegend / FieldGroup / FieldContent / FieldSeparator 规格未覆盖:
 *   仅把硬编码间距换成最近 token(gap-3→--space-3、gap-4→--space-4、gap-5→--space-4、
 *   mb-1.5→--space-2、h-5→--space-6),结构语义不变。
 * - 规格新增的部件按 markup 合同补为可选组件:FieldHeader(.field__header)、
 *   FieldRequired(aria-hidden "*")、FieldCount(aria-live="polite")、
 *   FieldControl(故意无样式的控件槽)、FieldSuccess(role="status")。
 * - 规格无动效规则,label 颜色变化不加 transition。
 */

/**
 * 状态协调片段:.field:has() 伪类 + data-[state=*] 镜像(见文件头注释)。
 * disabled 同时压暗 label/description/count/success(--opacity-disabled)。
 */
const disabledDim =
  "group-has-[:disabled]/field:opacity-[var(--opacity-disabled)] group-data-[state=disabled]/field:opacity-[var(--opacity-disabled)]"

const fieldVariants = cva("group/field w-full", {
  variants: {
    orientation: {
      vertical: "grid gap-[var(--space-2)] [&>.sr-only]:w-auto",
      horizontal:
        "flex flex-row items-center gap-[var(--space-4)] has-[>[data-slot=field-content]]:items-start *:data-[slot=field-label]:flex-auto has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px",
      responsive:
        "grid gap-[var(--space-2)] *:w-full @md/field-group:flex-row @md/field-group:items-center @md/field-group:gap-[var(--space-4)] @md/field-group:*:w-auto @md/field-group:has-[>[data-slot=field-content]]:items-start @md/field-group:*:data-[slot=field-label]:flex-auto [&>.sr-only]:w-auto @md/field-group:has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px",
    },
  },
  defaultVariants: {
    orientation: "vertical",
  },
})

function Field({
  className,
  orientation = "vertical",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof fieldVariants>) {
  return (
    <div
      role="group"
      data-slot="field"
      data-orientation={orientation}
      className={cn(fieldVariants({ orientation }), className)}
      {...props}
    />
  )
}

/** .field__header —— label 居左、可选字符计数居右。 */
function FieldHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-header"
      className={cn("flex items-baseline justify-between gap-[var(--space-4)]", className)}
      {...props}
    />
  )
}

function FieldLabel({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="field-label"
      className={cn(
        "w-fit cursor-pointer font-sans text-caption font-medium text-foreground-strong select-none",
        // focused child:label 提亮一档(--foreground),焦点环归控件
        "group-has-[:focus-visible]/field:text-foreground group-data-[state=focused]/field:text-foreground",
        // readonly child:label 降为 muted,控件仍可聚焦
        "group-has-[[readonly]]/field:text-muted-foreground group-data-[state=readonly]/field:text-muted-foreground",
        // disabled child:压暗 + 关闭 pointer cursor
        "group-has-[:disabled]/field:cursor-not-allowed group-data-[state=disabled]/field:cursor-not-allowed",
        disabledDim,
        // error:label 与错误文本同为 --destructive
        "group-data-[invalid=true]/field:text-destructive group-data-[state=error]/field:text-destructive",
        className,
      )}
      {...props}
    />
  )
}

/** .field__required —— "*" 只是标记,required 语义由控件自己的属性承载。 */
function FieldRequired({ className, children, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden="true"
      data-slot="field-required"
      className={cn("text-destructive", className)}
      {...props}
    >
      {children ?? "*"}
    </span>
  )
}

/** .field__count —— 可选字符计数。 */
function FieldCount({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-live="polite"
      data-slot="field-count"
      className={cn(
        "font-sans text-caption font-normal text-caption-foreground tabular-nums",
        disabledDim,
        className,
      )}
      {...props}
    />
  )
}

/** .field__control —— 故意无样式:控件槽,放进去的控件自带外观。 */
function FieldControl({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="field-control" className={cn(className)} {...props} />
}

function FieldTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-label"
      className={cn(
        "flex w-fit items-center gap-[var(--space-2)] font-sans text-caption font-medium text-foreground-strong",
        disabledDim,
        className,
      )}
      {...props}
    />
  )
}

function FieldContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-content"
      className={cn(
        "group/field-content flex flex-1 flex-col gap-[var(--space-0-5)] leading-snug",
        className,
      )}
      {...props}
    />
  )
}

/** .field__description —— helper 在任何校验状态下都保持 --muted-foreground。 */
function FieldDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="field-description"
      className={cn(
        "m-0 font-sans text-caption font-normal text-muted-foreground",
        disabledDim,
        "[&>a]:underline [&>a]:underline-offset-[var(--link-underline-offset)] [&>a:hover]:text-primary",
        className,
      )}
      {...props}
    />
  )
}

function FieldSeparator({
  children,
  className,
  ...props
}: React.ComponentProps<"div"> & {
  children?: React.ReactNode
}) {
  return (
    <div
      data-slot="field-separator"
      data-content={!!children}
      className={cn(
        "relative -my-[var(--space-2)] h-[var(--space-6)] text-caption group-data-[variant=outline]/field-group:-mb-[var(--space-2)]",
        className,
      )}
      {...props}
    >
      {/* my-0 抵消 Separator 自带的 --space-4 外围间距(绝对定位居中所需) */}
      <Separator className="absolute inset-0 top-1/2 my-0" />
      {children && (
        <span
          className="relative mx-auto block w-fit bg-background px-[var(--space-2)] text-muted-foreground"
          data-slot="field-separator-content"
        >
          {children}
        </span>
      )}
    </div>
  )
}

/** .field__error —— role="alert";无内容时不渲染(对应规格的 display:none)。 */
function FieldError({
  className,
  children,
  errors,
  ...props
}: React.ComponentProps<"div"> & {
  errors?: Array<{ message?: string } | undefined>
}) {
  const content = useMemo(() => {
    if (children) {
      return children
    }

    if (!errors?.length) {
      return null
    }

    const uniqueErrors = [...new Map(errors.map((error) => [error?.message, error])).values()]

    if (uniqueErrors?.length == 1) {
      return uniqueErrors[0]?.message
    }

    return (
      <ul className="ml-[var(--space-4)] flex list-disc flex-col gap-[var(--space-1)]">
        {uniqueErrors.map((error, index) => error?.message && <li key={index}>{error.message}</li>)}
      </ul>
    )
  }, [children, errors])

  if (!content) {
    return null
  }

  return (
    <div
      role="alert"
      data-slot="field-error"
      className={cn("m-0 font-sans text-caption font-medium text-destructive", className)}
      {...props}
    >
      {content}
    </div>
  )
}

/** .field__success —— role="status";无内容时不渲染(对应规格的 display:none)。 */
function FieldSuccess({ className, children, ...props }: React.ComponentProps<"p">) {
  if (!children) {
    return null
  }

  return (
    <p
      role="status"
      data-slot="field-success"
      className={cn("m-0 font-sans text-caption font-medium text-success", disabledDim, className)}
      {...props}
    >
      {children}
    </p>
  )
}

/* ===== 以下部件规格未覆盖:仅间距换 token,语义不变(见文件头注释) ===== */

function FieldSet({ className, ...props }: React.ComponentProps<"fieldset">) {
  return (
    <fieldset
      data-slot="field-set"
      className={cn(
        "flex flex-col gap-[var(--space-4)] has-[>[data-slot=checkbox-group]]:gap-[var(--space-3)] has-[>[data-slot=radio-group]]:gap-[var(--space-3)]",
        className,
      )}
      {...props}
    />
  )
}

function FieldLegend({
  className,
  variant = "legend",
  ...props
}: React.ComponentProps<"legend"> & { variant?: "legend" | "label" }) {
  return (
    <legend
      data-slot="field-legend"
      data-variant={variant}
      className={cn(
        "mb-[var(--space-2)] font-medium data-[variant=legend]:text-base",
        // variant=label → 规格 .field__label 的排印
        "data-[variant=label]:font-sans data-[variant=label]:text-caption data-[variant=label]:font-medium data-[variant=label]:text-foreground-strong",
        className,
      )}
      {...props}
    />
  )
}

function FieldGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-group"
      className={cn(
        "group/field-group @container/field-group flex w-full flex-col gap-[var(--space-4)] data-[slot=checkbox-group]:gap-[var(--space-3)] *:data-[slot=field-group]:gap-[var(--space-4)]",
        className,
      )}
      {...props}
    />
  )
}

export {
  Field,
  FieldContent,
  FieldControl,
  FieldCount,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldHeader,
  FieldLabel,
  FieldLegend,
  FieldRequired,
  FieldSeparator,
  FieldSet,
  FieldSuccess,
  FieldTitle,
}
