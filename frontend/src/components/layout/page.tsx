import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * 产品页面的共享构图原语（ADR 0019 / 0024）。
 * 只管理语义、宽度与间距；不读取数据、不判断权限。
 */

function Page({ className, ...props }: React.ComponentProps<"main">) {
  return (
    <main
      className={cn(
        "mx-auto flex w-full max-w-[1400px] flex-col gap-10 px-6 py-10 max-sm:gap-8 max-sm:px-4 max-sm:py-8",
        className,
      )}
      data-slot="page"
      id="main-content"
      {...props}
    />
  )
}

function PageHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      className={cn(
        "flex items-start justify-between gap-8 border-b border-border pb-8 max-md:flex-col max-md:gap-5",
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
      className={cn("flex min-w-0 max-w-[72ch] flex-col gap-3", className)}
      data-slot="page-header-content"
      {...props}
    />
  )
}

function PageEyebrow({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn(
        "m-0 font-mono text-xs font-medium tracking-wide text-foreground uppercase",
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
        "m-0 text-[length:var(--text-heading)] leading-[var(--text-heading--line-height)] font-semibold text-pretty text-foreground max-sm:text-2xl",
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
      className={cn("m-0 max-w-[68ch] text-base leading-normal text-muted-foreground", className)}
      data-slot="page-description"
      {...props}
    />
  )
}

function PageActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex shrink-0 flex-wrap items-center justify-end gap-3 max-md:w-full max-md:justify-start",
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
      className={cn("flex min-w-0 flex-col gap-5", className)}
      data-slot="page-section"
      {...props}
    />
  )
}

function PageSectionHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      className={cn(
        "flex items-end justify-between gap-6 max-md:flex-col max-md:items-start max-md:gap-3",
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
      className={cn("flex min-w-0 flex-col gap-1", className)}
      data-slot="page-section-header-content"
      {...props}
    />
  )
}

function PageSectionTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      className={cn("m-0 text-xl font-semibold leading-normal text-foreground", className)}
      data-slot="page-section-title"
      {...props}
    />
  )
}

function PageSectionDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn("m-0 max-w-[68ch] text-sm leading-normal text-muted-foreground", className)}
      data-slot="page-section-description"
      {...props}
    />
  )
}

function PageSectionActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-wrap items-center gap-3", className)}
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
          "flex flex-wrap items-end gap-4 border-y border-border bg-muted px-5 py-4 max-sm:-mx-4 max-sm:px-4",
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
        "min-w-0 overflow-hidden rounded-md border border-border bg-background",
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
        "flex items-start justify-between gap-5 border-b border-border bg-card px-5 py-4 max-sm:flex-col",
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
        "border-t border-border bg-card px-5 py-4 text-sm text-muted-foreground",
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
        "m-0 grid grid-cols-2 gap-x-8 border-t border-border max-md:grid-cols-1",
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
        "grid min-w-0 grid-cols-[minmax(8rem,0.4fr)_minmax(0,1fr)] gap-4 border-b border-border py-4 max-sm:grid-cols-1 max-sm:gap-1",
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
      className={cn("text-sm leading-normal font-medium text-muted-foreground", className)}
      data-slot="description-term"
      {...props}
    />
  )
}

function DescriptionDetails({ className, ...props }: React.ComponentProps<"dd">) {
  return (
    <dd
      className={cn("m-0 min-w-0 text-base leading-normal text-foreground", className)}
      data-slot="description-details"
      {...props}
    />
  )
}

function FormSection({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "grid grid-cols-[minmax(14rem,0.42fr)_minmax(0,1fr)] gap-10 border-t border-border pt-6 max-lg:grid-cols-1 max-lg:gap-5",
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
      className={cn("flex min-w-0 flex-col gap-2", className)}
      data-slot="form-section-header"
      {...props}
    />
  )
}

function FormSectionTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      className={cn("m-0 text-base font-semibold leading-normal text-foreground", className)}
      data-slot="form-section-title"
      {...props}
    />
  )
}

function FormSectionDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn("m-0 text-sm leading-normal text-muted-foreground", className)}
      data-slot="form-section-description"
      {...props}
    />
  )
}

function FormSectionContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex min-w-0 max-w-3xl flex-col gap-5", className)}
      data-slot="form-section-content"
      {...props}
    />
  )
}

function AuthPanel({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "w-full max-w-lg rounded-md border border-border bg-card p-8 max-sm:p-6",
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
      className={cn("mb-6 flex flex-col gap-2", className)}
      data-slot="auth-panel-header"
      {...props}
    />
  )
}

function AuthPanelTitle({ className, ...props }: React.ComponentProps<"h1">) {
  return (
    <h1
      className={cn(
        "m-0 text-[length:var(--text-display)] leading-[var(--text-display--line-height)] font-bold text-pretty text-foreground max-sm:text-[length:var(--text-heading)]",
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
      className={cn("m-0 text-sm leading-normal text-muted-foreground", className)}
      data-slot="auth-panel-description"
      {...props}
    />
  )
}

function AuthPanelContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-col gap-5", className)}
      data-slot="auth-panel-content"
      {...props}
    />
  )
}

function AuthPanelFooter({ className, ...props }: React.ComponentProps<"footer">) {
  return (
    <footer
      className={cn("mt-6 border-t border-border pt-5 text-sm text-muted-foreground", className)}
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
