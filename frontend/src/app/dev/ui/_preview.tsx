import type { ReactNode } from "react"

function PreviewPage({
  children,
  description,
  title,
}: {
  readonly children: ReactNode
  readonly description: string
  readonly title: string
}) {
  return (
    <main className="mx-auto min-h-dvh max-w-[var(--doc-container-max)] px-[var(--space-6)] py-[var(--space-16)] text-foreground">
      <header className="border-b-[length:var(--border-width)] border-border pb-[var(--space-8)]">
        <p className="font-sans text-[length:var(--text-caption-up)] leading-[var(--text-caption-up--line-height)] tracking-[var(--text-caption-up--letter-spacing)] font-medium text-primary uppercase">
          Component
        </p>
        <h1 className="mt-[var(--space-3)] font-display text-[length:var(--text-display-md)] leading-[var(--text-display-md--line-height)] font-normal tracking-[var(--text-display-md--letter-spacing)]">
          {title}
        </h1>
        <p className="mt-[var(--space-4)] max-w-[72ch] font-sans text-[length:var(--text-body-md)] leading-[var(--text-body-md--line-height)] text-muted-foreground">
          {description}
        </p>
      </header>
      <div className="grid gap-[var(--space-8)] py-[var(--space-8)]">{children}</div>
    </main>
  )
}

function PreviewSection({
  children,
  title,
}: {
  readonly children: ReactNode
  readonly title: string
}) {
  return (
    <section className="grid gap-[var(--space-6)] rounded-[var(--radius-lg)] border-[length:var(--border-width)] border-border-soft bg-surface-soft p-[var(--space-8)]">
      <h2 className="font-sans text-[length:var(--text-title-md)] leading-[var(--text-title-md--line-height)] font-medium">
        {title}
      </h2>
      {children}
    </section>
  )
}

export { PreviewPage, PreviewSection }
