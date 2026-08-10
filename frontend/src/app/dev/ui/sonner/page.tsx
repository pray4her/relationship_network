"use client"

import { Button } from "@/components/ui/button"
import {
  type ToastVariant,
  toastPartClassNames,
  toastVariantIcons,
  toastVariants,
} from "@/components/ui/sonner"
import { cn } from "@/lib/utils"

/**
 * Toast (sonner) 预览页 —— 对应 showcase/toast.html:
 * variants 全解剖样品 + close 状态矩阵 + 生命周期 + 堆叠/放置 + token 对照。
 * 状态经 data-[state=*] 镜像静态渲染(见 ui/sonner.tsx 注释);不触发真实通知,
 * 样品复用 sonner.tsx 导出的同一套 token 类与图标。
 * showcase 的 live demo(实时推入/暂停)依赖控制器,静态页不覆盖。
 */
type ToastSampleProps = {
  readonly variant: ToastVariant
  readonly title: string
  readonly description?: string
  readonly action?: string
  readonly state?: "entering" | "visible" | "exiting"
  readonly closeState?: "hover" | "active" | "focus-visible"
  readonly closeDisabled?: boolean
}

/** 静态 toast 样品:规格 anatomy(icon · body · close),类全部来自 ui/sonner.tsx。 */
function ToastSample({
  variant,
  title,
  description,
  action,
  state,
  closeState,
  closeDisabled,
}: ToastSampleProps) {
  return (
    <div className={cn(toastVariants({ variant }))} data-state={state}>
      <span className={toastPartClassNames.icon} data-icon="">
        {toastVariantIcons[variant]}
      </span>
      <div className={toastPartClassNames.content}>
        <p className={toastPartClassNames.title}>{title}</p>
        {description ? <p className={toastPartClassNames.description}>{description}</p> : null}
        {action ? (
          <div className="mt-[var(--space-3)]">
            <Button size="sm" variant="secondary">
              {action}
            </Button>
          </div>
        ) : null}
      </div>
      <button
        aria-label={`Dismiss ${title}`}
        className={toastPartClassNames.close}
        data-state={closeState}
        disabled={closeDisabled}
        tabIndex={closeState || closeDisabled ? -1 : undefined}
        type="button"
      >
        {toastVariantIcons.close}
      </button>
    </div>
  )
}

const variants: readonly {
  variant: ToastVariant
  title: string
  description: string
  action: string
}[] = [
  {
    variant: "neutral",
    title: "Draft saved locally",
    description: "Offline edits sync when you reconnect.",
    action: "Open draft",
  },
  {
    variant: "info",
    title: "Matching index is syncing",
    description: "New embeddings appear in search within a few minutes.",
    action: "View status",
  },
  {
    variant: "success",
    title: "Invite sent",
    description: "Mei Chen will receive an email to join Acme.",
    action: "View members",
  },
  {
    variant: "warning",
    title: "Subscription expires in 5 days",
    description: "The tenant becomes read-only after expiry.",
    action: "Renew plan",
  },
  {
    variant: "destructive",
    title: "Document upload failed",
    description: "File exceeds the 25 MB limit. Compress and retry.",
    action: "Try again",
  },
]

const closeStates = [
  { label: "default", title: "Default close", description: "Resting control.", props: {} },
  {
    label: "hover",
    title: "Hover close",
    description: "Accent surface.",
    props: { closeState: "hover" },
  },
  {
    label: "active",
    title: "Active close",
    description: "Pressed selection surface.",
    props: { closeState: "active" },
  },
  {
    label: "focus-visible",
    title: "Focused close",
    description: "Shared focus ring.",
    props: { closeState: "focus-visible" },
  },
  {
    label: "disabled",
    title: "Disabled close",
    description: "Native disabled + opacity.",
    props: { closeDisabled: true },
  },
] as const

const lifecycleStates = [
  {
    label: "entering",
    variant: "info",
    title: "Entering",
    description: "Opacity 0 · translated by --space-4.",
  },
  {
    label: "visible",
    variant: "success",
    title: "Visible",
    description: "Resting pose — full opacity, no offset.",
  },
  {
    label: "exiting",
    variant: "warning",
    title: "Exiting",
    description: "Fading out · same --space-4 travel.",
  },
] as const

const tokenLegend = [
  { term: "surface", detail: "--popover · --border · --shadow-lift" },
  { term: "text", detail: "--foreground · --muted-foreground" },
  { term: "accent", detail: "--info / --success / --warning / --destructive" },
  {
    term: "radius / space",
    detail: "--radius-lg · pad --space-4 · stack gap --space-3 · inset --space-6",
  },
  { term: "motion", detail: "--duration-normal · --ease-standard · travel --space-4" },
  { term: "layer", detail: "--z-popover (gap: no --z-toast)" },
] as const

export default function SonnerPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Toast</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Elevated transient notices. Surface stays readable (--popover + --shadow-lift); status
          speaks through the accent icon and leading edge. Static samples reuse the exact token
          classes the Toaster passes to sonner.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="variants-heading">
        <h2 className="mb-2 text-xl" id="variants-heading">
          Variants — elevated surface, semantic accent
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Neutral → info → success → warning → destructive. Each row shows the full anatomy: icon,
          title, description, optional action, close.
        </p>
        <div className="grid max-w-[calc(var(--space-16)*6)] gap-[var(--space-3)]">
          {variants.map((sample) => (
            <ToastSample
              action={sample.action}
              description={sample.description}
              key={sample.variant}
              title={sample.title}
              variant={sample.variant}
              {...(sample.variant === "destructive"
                ? { closeState: "focus-visible" as const }
                : {})}
            />
          ))}
        </div>
        <p className="mt-6 max-w-xl text-muted-foreground text-xs">
          Accent (icon + inset leading edge) maps to --info / --success / --warning / --destructive
          (neutral → --muted-foreground). The destructive close shows
          data-state=&#34;focus-visible&#34;.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="close-states-heading">
        <h2 className="mb-2 text-xl" id="close-states-heading">
          Close action state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Identical Toast geometry with the private close action held in every applicable state.
        </p>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
          {closeStates.map((sample) => (
            <div className="grid content-start gap-3" key={sample.label}>
              <span className="text-muted-foreground text-xs">{sample.label}</span>
              <ToastSample
                description={sample.description}
                title={sample.title}
                variant="neutral"
                {...sample.props}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="lifecycle-heading">
        <h2 className="mb-2 text-xl" id="lifecycle-heading">
          Lifecycle — entering · visible · exiting
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Static data-state poses freeze each frame. Motion distance is --space-4; timing is
          --duration-normal / --ease-standard (driven by the sonner controller at runtime).
          Entering/exiting render at opacity 0 by design.
        </p>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
          {lifecycleStates.map((sample) => (
            <div className="grid content-start gap-3" key={sample.label}>
              <span className="text-muted-foreground text-xs">{sample.label}</span>
              <ToastSample
                description={sample.description}
                state={sample.label}
                title={sample.title}
                variant={sample.variant}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="stack-heading">
        <h2 className="mb-2 text-xl" id="stack-heading">
          Stack &amp; placement
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Viewport gap --space-3, inset --space-6, layer --z-popover. Bottom placements stack upward
          so the newest toast sits nearest the edge.
        </p>
        <div className="relative min-h-[calc(var(--space-24)*4)] overflow-hidden rounded-[var(--radius-lg)] border border-border-soft bg-surface-soft">
          <div
            aria-atomic={false}
            aria-live="polite"
            aria-relevant="additions text"
            className="absolute right-[var(--space-6)] bottom-[var(--space-6)] flex w-[calc(var(--space-16)*6)] max-w-[calc(100%-(var(--space-6)*2))] flex-col-reverse gap-[var(--space-3)]"
          >
            <ToastSample
              description="Newest — nearest the bottom edge."
              title="Profile published"
              variant="success"
            />
            <ToastSample description="Middle of the stack." title="Index syncing" variant="info" />
            <ToastSample
              description="Oldest — farthest from the edge."
              title="Draft autosaved"
              variant="neutral"
            />
          </div>
        </div>
      </section>

      <section className="py-8" aria-labelledby="tokens-heading">
        <h2 className="mb-2 text-xl" id="tokens-heading">
          Token mapping (summary)
        </h2>
        <dl className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-x-6 gap-y-3">
          {tokenLegend.map((entry) => (
            <div key={entry.term}>
              <dt className="text-muted-foreground text-xs">{entry.term}</dt>
              <dd className="mt-0.5 text-foreground-body text-sm">{entry.detail}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  )
}
