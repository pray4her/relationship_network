import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 产品页面的共享构图原语。
 *
 * 这些组件只管理语义、宽度与间距，不读取数据、判断权限或拥有业务状态。
 * 页面仍负责选择标题层级、关联 aria-labelledby，并组合真实 UI 原语。
 */

function Page({ className, ...props }: React.ComponentProps<"main">) {
  return (
    <main
      className={cn(
        "mx-auto flex w-full max-w-[1400px] flex-col gap-[var(--space-10)] px-[var(--space-6)] py-[var(--space-10)] max-sm:gap-[var(--space-8)] max-sm:px-[var(--space-4)] max-sm:py-[var(--space-8)]",
        className,
      )}
      data-slot="page"
      {...props}
    />
  )
}

function PageHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      className={cn(
        "flex items-start justify-between gap-[var(--space-8)] border-border-soft border-b-[length:var(--border-width)] pb-[var(--space-8)] max-md:flex-col max-md:gap-[var(--space-5)]",
        className,
      )}
      data-slot="page-header"
      {...props}
    />
  )
}

function PageHeaderContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("min-w-0 max-w-[72ch] space-y-[var(--space-3)]", className)}
      data-slot="page-header-content"
      {...props}
    />
  )
}

function PageEyebrow({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn(
        "m-0 font-mono text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] font-medium tracking-[var(--tracking-label)] text-muted-foreground uppercase",
        className,
      )}
      data-slot="page-eyebrow"
      {...props}
    />
  )
}

function PageTitle({ className, ...props }: React.ComponentProps<"h1">) {
  return (
    <h1
      className={cn(
        "m-0 font-display text-[length:var(--text-display-lg)] leading-[var(--text-display-lg--line-height)] font-normal tracking-[var(--text-display-lg--letter-spacing)] text-foreground max-sm:text-[length:var(--text-display-md)] max-sm:leading-[var(--text-display-md--line-height)]",
        className,
      )}
      data-slot="page-title"
      {...props}
    />
  )
}

function PageDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn(
        "m-0 max-w-[68ch] text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)] text-muted-foreground",
        className,
      )}
      data-slot="page-description"
      {...props}
    />
  )
}

function PageActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex shrink-0 flex-wrap items-center justify-end gap-[var(--space-3)] max-md:w-full max-md:justify-start",
        className,
      )}
      data-slot="page-actions"
      {...props}
    />
  )
}

function PageSection({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn("flex min-w-0 flex-col gap-[var(--space-5)]", className)}
      data-slot="page-section"
      {...props}
    />
  )
}

function PageSectionHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      className={cn(
        "flex items-end justify-between gap-[var(--space-6)] max-md:flex-col max-md:items-start max-md:gap-[var(--space-3)]",
        className,
      )}
      data-slot="page-section-header"
      {...props}
    />
  )
}

function PageSectionHeaderContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("min-w-0 space-y-[var(--space-1)]", className)}
      data-slot="page-section-header-content"
      {...props}
    />
  )
}

function PageSectionTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      className={cn(
        "m-0 font-sans text-[length:var(--text-title-lg)] leading-[var(--text-title-lg--line-height)] font-medium text-foreground",
        className,
      )}
      data-slot="page-section-title"
      {...props}
    />
  )
}

function PageSectionDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn(
        "m-0 max-w-[68ch] text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] text-muted-foreground",
        className,
      )}
      data-slot="page-section-description"
      {...props}
    />
  )
}

function PageSectionActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-wrap items-center gap-[var(--space-3)]", className)}
      data-slot="page-section-actions"
      {...props}
    />
  )
}

function PageToolbar({ className, render, ...props }: useRender.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(
          "flex flex-wrap items-end gap-[var(--space-4)] border-border-soft border-y-[length:var(--border-width)] bg-surface-soft px-[var(--space-5)] py-[var(--space-4)] max-sm:-mx-[var(--space-4)] max-sm:px-[var(--space-4)]",
          className,
        ),
      },
      props,
    ),
    render,
    state: { slot: "page-toolbar" },
  })
}

function DataRegion({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "min-w-0 overflow-hidden rounded-[var(--radius-lg)] border-[length:var(--border-width)] border-border bg-background",
        className,
      )}
      data-slot="data-region"
      {...props}
    />
  )
}

function DataRegionHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-[var(--space-5)] border-border-soft border-b-[length:var(--border-width)] bg-card px-[var(--space-5)] py-[var(--space-4)] max-sm:flex-col",
        className,
      )}
      data-slot="data-region-header"
      {...props}
    />
  )
}

function DataRegionContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("min-w-0", className)} data-slot="data-region-content" {...props} />
}

function DataRegionFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "border-border-soft border-t-[length:var(--border-width)] bg-card px-[var(--space-5)] py-[var(--space-4)] text-[length:var(--text-body-sm)] text-muted-foreground",
        className,
      )}
      data-slot="data-region-footer"
      {...props}
    />
  )
}

function DescriptionList({ className, ...props }: React.ComponentProps<"dl">) {
  return (
    <dl
      className={cn(
        "m-0 grid grid-cols-2 gap-x-[var(--space-8)] border-border-soft border-t-[length:var(--border-width)] max-md:grid-cols-1",
        className,
      )}
      data-slot="description-list"
      {...props}
    />
  )
}

function DescriptionItem({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "grid min-w-0 grid-cols-[minmax(8rem,0.4fr)_minmax(0,1fr)] gap-[var(--space-4)] border-border-soft border-b-[length:var(--border-width)] py-[var(--space-4)] max-sm:grid-cols-1 max-sm:gap-[var(--space-1)]",
        className,
      )}
      data-slot="description-item"
      {...props}
    />
  )
}

function DescriptionTerm({ className, ...props }: React.ComponentProps<"dt">) {
  return (
    <dt
      className={cn(
        "text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] font-medium text-muted-foreground",
        className,
      )}
      data-slot="description-term"
      {...props}
    />
  )
}

function DescriptionDetails({ className, ...props }: React.ComponentProps<"dd">) {
  return (
    <dd
      className={cn(
        "m-0 min-w-0 text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)] text-foreground-body",
        className,
      )}
      data-slot="description-details"
      {...props}
    />
  )
}

function FormSection({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "grid grid-cols-[minmax(14rem,0.42fr)_minmax(0,1fr)] gap-[var(--space-10)] border-border-soft border-t-[length:var(--border-width)] pt-[var(--space-6)] max-lg:grid-cols-1 max-lg:gap-[var(--space-5)]",
        className,
      )}
      data-slot="form-section"
      {...props}
    />
  )
}

function FormSectionHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      className={cn("min-w-0 space-y-[var(--space-2)]", className)}
      data-slot="form-section-header"
      {...props}
    />
  )
}

function FormSectionTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      className={cn(
        "m-0 text-[length:var(--text-title-md)] leading-[var(--text-title-md--line-height)] font-medium text-foreground",
        className,
      )}
      data-slot="form-section-title"
      {...props}
    />
  )
}

function FormSectionDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn(
        "m-0 text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] text-muted-foreground",
        className,
      )}
      data-slot="form-section-description"
      {...props}
    />
  )
}

function FormSectionContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("min-w-0 max-w-3xl space-y-[var(--space-5)]", className)}
      data-slot="form-section-content"
      {...props}
    />
  )
}

function AuthPanel({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "w-full max-w-lg rounded-[var(--radius-lg)] border-[length:var(--border-width)] border-border bg-card p-[var(--space-8)] shadow-subtle max-sm:p-[var(--space-6)]",
        className,
      )}
      data-slot="auth-panel"
      {...props}
    />
  )
}

function AuthPanelHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      className={cn("mb-[var(--space-6)] space-y-[var(--space-2)]", className)}
      data-slot="auth-panel-header"
      {...props}
    />
  )
}

function AuthPanelTitle({ className, ...props }: React.ComponentProps<"h1">) {
  return (
    <h1
      className={cn(
        "m-0 font-display text-[length:var(--text-display-sm)] leading-[var(--text-display-sm--line-height)] font-normal tracking-[var(--text-display-sm--letter-spacing)] text-foreground",
        className,
      )}
      data-slot="auth-panel-title"
      {...props}
    />
  )
}

function AuthPanelDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn(
        "m-0 text-[length:var(--text-body-sm)] leading-[var(--text-body-sm--line-height)] text-muted-foreground",
        className,
      )}
      data-slot="auth-panel-description"
      {...props}
    />
  )
}

function AuthPanelContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("space-y-[var(--space-5)]", className)}
      data-slot="auth-panel-content"
      {...props}
    />
  )
}

function AuthPanelFooter({ className, ...props }: React.ComponentProps<"footer">) {
  return (
    <footer
      className={cn(
        "mt-[var(--space-6)] border-border-soft border-t-[length:var(--border-width)] pt-[var(--space-5)] text-[length:var(--text-body-sm)] text-muted-foreground",
        className,
      )}
      data-slot="auth-panel-footer"
      {...props}
    />
  )
}

export {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelFooter,
  AuthPanelHeader,
  AuthPanelTitle,
  DataRegion,
  DataRegionContent,
  DataRegionFooter,
  DataRegionHeader,
  DescriptionDetails,
  DescriptionItem,
  DescriptionList,
  DescriptionTerm,
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
  Page,
  PageActions,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionActions,
  PageSectionDescription,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
  PageToolbar,
}
