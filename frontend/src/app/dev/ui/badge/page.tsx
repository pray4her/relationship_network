"use client"

import { Badge } from "@/components/ui/badge"

/**
 * Badge 预览页 —— 对应 showcase/badge.html:
 * dismiss 动作状态矩阵 + variant × style × 内容矩阵 + sizes + parts。
 * dismiss 交互态经 data-[state=*] 镜像静态渲染(见 ui/badge.tsx 注释)。
 */
const specVariants = [
  { name: "neutral", label: "Draft" },
  { name: "primary", label: "Featured" },
  { name: "info", label: "Connected" },
  { name: "success", label: "Active" },
  { name: "warning", label: "Expiring" },
  { name: "destructive", label: "Suspended" },
] as const
const styles = ["subtle", "solid", "outline"] as const
const dismissStates = [
  { label: "default", props: {} },
  { label: "hover", props: { "data-state": "hover", tabIndex: -1 } },
  { label: "active", props: { "data-state": "active", tabIndex: -1 } },
  { label: "focus-visible", props: { "data-state": "focus-visible", tabIndex: -1 } },
  { label: "disabled", props: { disabled: true } },
] as const

const noop = () => undefined

const checkIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path
      d="m5 12.5 4.5 4.5L19 7.5"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const warningIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path d="M12 4 21 19.5H3L12 4Z" stroke="currentColor" strokeLinejoin="round" />
    <path d="M12 10v4" stroke="currentColor" strokeLinecap="round" />
    <circle cx="12" cy="16.8" fill="currentColor" r="0.5" />
  </svg>
)

const infoIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.5" stroke="currentColor" />
    <path d="M12 11v5" stroke="currentColor" strokeLinecap="round" />
    <circle cx="12" cy="8" fill="currentColor" r="0.5" />
  </svg>
)

const thClass = "border-border-soft border-r border-b bg-surface-soft p-3 text-left align-middle"
const tdClass = "border-border-soft border-r border-b p-3 align-middle"
const rowHeadClass = `${tdClass} bg-card`
const cardClass =
  "grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6"

export default function BadgePreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Badge</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          A non-interactive status label. Variants are semantic roles resolved to the semantic
          status tokens; the three styles (subtle / solid / outline) share one outer geometry via a
          constant border, transparent when unused. The only focusable part is the optional dismiss
          button.
        </p>
      </header>

      <section
        className="border-border-soft border-b py-8"
        aria-labelledby="dismiss-matrix-heading"
      >
        <h2 className="mb-2 text-xl" id="dismiss-matrix-heading">
          Dismiss action state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The badge remains a status label; only the nested button is interactive. States mirrored
          via data-state attributes.
        </p>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-6">
          {dismissStates.map((state) => (
            <div className="grid justify-items-start gap-3" key={state.label}>
              <p className="text-muted-foreground text-xs">{state.label}</p>
              <Badge
                dismissLabel={`Dismiss Location Berlin, ${state.label}`}
                dismissProps={state.props}
                onDismiss={noop}
                variant="primary"
              >
                Location: Berlin
              </Badge>
            </div>
          ))}
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Full state matrix — variant × style × content
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Every semantic role × every style, each with the four content configurations (text · icon
          · dot · dismiss). No primary tint exists — subtle primary keeps the neutral fill by
          design.
        </p>

        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-popover shadow-subtle">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr>
                <th className={thClass} scope="col">
                  Variant
                </th>
                {styles.map((style) => (
                  <th className={thClass} key={style} scope="col">
                    {style}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {specVariants.map((variant) => (
                <tr key={variant.name}>
                  <th className={rowHeadClass} scope="row">
                    {variant.name}
                    <span className="block text-muted-foreground text-xs">
                      text · icon · dot · dismiss
                    </span>
                  </th>
                  {styles.map((style) => (
                    <td className={tdClass} key={style}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge style={style} variant={variant.name}>
                          {variant.label}
                        </Badge>
                        <Badge style={style} variant={variant.name}>
                          {checkIcon}
                          {variant.label}
                        </Badge>
                        <Badge dot style={style} variant={variant.name}>
                          {variant.label}
                        </Badge>
                        <Badge
                          dismissLabel={`Dismiss ${variant.label}`}
                          onDismiss={noop}
                          style={style}
                          variant={variant.name}
                        >
                          {variant.label}
                        </Badge>
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="sizes-heading">
        <h2 className="mb-2 text-xl" id="sizes-heading">
          Sizes
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className={cardClass}>
            <h3 className="text-base font-medium">md</h3>
            <div className="flex flex-wrap items-center gap-3">
              <Badge dot variant="success">
                Verified
              </Badge>
              <Badge style="solid" variant="primary">
                Pro
              </Badge>
              <Badge style="outline" variant="warning">
                Trial
              </Badge>
            </div>
            <p className="text-muted-foreground text-xs">
              --text-caption · padding --space-1/--space-3
            </p>
          </article>
          <article className={cardClass}>
            <h3 className="text-base font-medium">sm</h3>
            <div className="flex flex-wrap items-center gap-3">
              <Badge dot size="sm" variant="success">
                Verified
              </Badge>
              <Badge size="sm" style="solid" variant="primary">
                Pro
              </Badge>
              <Badge size="sm" style="outline" variant="warning">
                Trial
              </Badge>
            </div>
            <p className="text-muted-foreground text-xs">
              --text-caption-up (uppercase treatment) · padding --space-0-5/--space-2
            </p>
          </article>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="parts-heading">
        <h2 className="mb-2 text-xl" id="parts-heading">
          Parts
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className={cardClass}>
            <h3 className="text-base font-medium">Text only</h3>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="neutral">Draft</Badge>
              <Badge style="solid" variant="destructive">
                Overdue
              </Badge>
              <Badge size="sm" style="outline" variant="neutral">
                Free
              </Badge>
            </div>
          </article>
          <article className={cardClass}>
            <h3 className="text-base font-medium">Leading icon</h3>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="success">{checkIcon}Matched</Badge>
              <Badge style="outline" variant="warning">
                {warningIcon}Expiring
              </Badge>
              <Badge style="solid" variant="info">
                {infoIcon}Synced
              </Badge>
            </div>
            <p className="text-muted-foreground text-xs">currentColor at --icon-size-xs</p>
          </article>
          <article className={cardClass}>
            <h3 className="text-base font-medium">Status dot</h3>
            <div className="flex flex-wrap items-center gap-3">
              <Badge dot variant="success">
                Online
              </Badge>
              <Badge dot variant="info">
                Connected
              </Badge>
              <Badge dot variant="destructive">
                Offline
              </Badge>
            </div>
            <p className="text-muted-foreground text-xs">--space-2 circle in the variant token</p>
          </article>
          <article className={cardClass}>
            <h3 className="text-base font-medium">Dismissible</h3>
            <div className="flex flex-wrap items-center gap-3">
              <Badge
                dismissLabel="Remove filter: Location Berlin"
                onDismiss={noop}
                variant="neutral"
              >
                Location: Berlin
              </Badge>
              <Badge
                dismissLabel="Remove filter: Role Engineer"
                onDismiss={noop}
                style="outline"
                variant="primary"
              >
                Role: Engineer
              </Badge>
              <Badge
                dismissLabel="Remove filter: Plan Pro"
                onDismiss={noop}
                style="solid"
                variant="primary"
              >
                Plan: Pro
              </Badge>
            </div>
            <p className="text-muted-foreground text-xs">
              The only focusable part; hover uses --accent, focus uses the shared ring
            </p>
          </article>
        </div>
      </section>

      <section className="py-8" aria-labelledby="aliases-heading">
        <h2 className="mb-2 text-xl" id="aliases-heading">
          API aliases
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Existing API names mapped to the nearest spec: default→solid primary, secondary/ghost→
          subtle neutral, destructive→subtle destructive, outline→outline neutral, link→outline
          primary.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <Badge variant="default">Default (=solid primary)</Badge>
          <Badge variant="secondary">Secondary (=subtle neutral)</Badge>
          <Badge variant="ghost">Ghost (=subtle neutral)</Badge>
          <Badge variant="destructive">Destructive (=subtle)</Badge>
          <Badge variant="outline">Outline (=outline neutral)</Badge>
          <Badge variant="link">Link (=outline primary)</Badge>
        </div>
      </section>
    </main>
  )
}
