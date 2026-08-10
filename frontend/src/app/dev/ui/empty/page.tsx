import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"

/**
 * EmptyState 预览页 —— 对应 showcase/empty-state.html:
 * 四场景对比 + media 选项 + actions 组合/状态 + 卡片上下文,共四节。
 * 组件自身无交互态(规格);actions 的 hover/focus/disabled/loading
 * 全部经 Button 的 data-[state=*] 镜像静态渲染(见 ui/button.tsx 注释)。
 */

const plusIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path d="M12 4v16M4 12h16" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const searchIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <circle cx="11" cy="11" r="6" stroke="currentColor" />
    <path d="m15.5 15.5 4 4" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const inboxIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path d="M4 6h16v12H4z" stroke="currentColor" strokeLinejoin="round" />
    <path d="M4 13h5l1.5 2h3L15 13h5" stroke="currentColor" strokeLinejoin="round" />
  </svg>
)

const warningIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path d="M12 4 21 19H3L12 4z" stroke="currentColor" strokeLinejoin="round" />
    <path d="M12 10v4" stroke="currentColor" strokeLinecap="round" />
    <circle cx="12" cy="16.5" r="0.5" fill="currentColor" />
  </svg>
)

const briefcaseIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path d="M5 8h14v10H5z" stroke="currentColor" strokeLinejoin="round" />
    <path d="M9 8V6h6v2" stroke="currentColor" strokeLinejoin="round" />
    <path d="M5 12h14" stroke="currentColor" />
  </svg>
)

const illustration = (
  <svg aria-hidden="true" fill="none" height="96" viewBox="0 0 160 96" width="160">
    <path d="M24 76 44 36h72l20 40" stroke="currentColor" strokeLinejoin="round" />
    <path d="M24 76h112" stroke="currentColor" strokeLinecap="round" />
    <path d="M64 36l6 14h20l6-14" stroke="currentColor" strokeLinejoin="round" />
    <path d="M80 12v8M64 18l4 6M96 18l-4 6" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const regionClass = "rounded-[var(--radius-lg)] border border-border bg-background"
const actionLabelClass =
  "font-sans font-medium text-[length:var(--text-caption-up)] leading-[var(--text-caption-up--line-height)] tracking-[var(--text-caption-up--letter-spacing)] uppercase text-caption-foreground"

export default function EmptyPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Empty State</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Content-driven placeholders for vacant regions. All four semantic scenarios render in one
          preview; actions are real Button components, never restyled locally.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="scenarios-heading">
        <h2 className="mb-2 text-xl" id="scenarios-heading">
          State matrix — all scenarios in one preview
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          First-use, no-results, no-data, and error/recovery side by side — only the chip tint and
          glyph color change per variant; hierarchy, rhythm, and measure stay identical.
        </p>

        <div className="grid grid-cols-2 gap-[var(--space-6)] max-md:grid-cols-1">
          <div className={regionClass}>
            <Empty aria-labelledby="es-first-title" role="region" variant="first-use">
              <EmptyMedia variant="icon">{plusIcon}</EmptyMedia>
              <EmptyTitle id="es-first-title">Create your first company</EmptyTitle>
              <EmptyDescription>
                Companies are the heart of your workspace — profiles, documents, and job postings
                all hang off one. Add the first to unlock the rest.
              </EmptyDescription>
              <EmptyContent>
                <Button>Add a company</Button>
                <Button variant="secondary">Import from file</Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-results-title" role="region" variant="no-results">
              <EmptyMedia variant="icon">{searchIcon}</EmptyMedia>
              <EmptyTitle id="es-results-title">No matches for “quantum barista”</EmptyTitle>
              <EmptyDescription>
                Nothing in the index fits that query. Check the spelling, loosen a filter, or try a
                broader skill.
              </EmptyDescription>
              <EmptyContent>
                <Button>Clear filters</Button>
                <Button variant="link">Search tips</Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-data-title" role="region" variant="no-data">
              <EmptyMedia variant="icon">{inboxIcon}</EmptyMedia>
              <EmptyTitle id="es-data-title">No documents yet</EmptyTitle>
              <EmptyDescription>
                Company files live in a private bucket and never get a public URL. Upload the first
                one to start the paper trail.
              </EmptyDescription>
              <EmptyContent>
                <Button>Upload documents</Button>
                <Button variant="link">Document guide</Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-error-title" role="region" variant="error">
              <EmptyMedia variant="icon">{warningIcon}</EmptyMedia>
              <EmptyTitle id="es-error-title">Couldn’t load the member list</EmptyTitle>
              <EmptyDescription>
                The request timed out before the roster arrived. Your data is safe — retry, or check
                platform health if it keeps happening.
              </EmptyDescription>
              <EmptyContent>
                <Button>Retry</Button>
                <Button variant="link">Platform health</Button>
              </EmptyContent>
            </Empty>
          </div>
        </div>
        <p className="mt-6 max-w-2xl text-caption-foreground text-xs">
          Chip system: first-use info-soft / info, no-results surface-soft, no-data card (one card
          tone deeper so the two neutrals stay distinguishable), error destructive-soft /
          destructive. Titles read at --text-title-lg in foreground; descriptions at --text-body-md
          in muted-foreground.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="media-heading">
        <h2 className="mb-2 text-xl" id="media-heading">
          Media — icon chip, illustration, or none
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The media slot is optional: an icon chip (--avatar-size-xl with an --icon-size-lg glyph),
          a content-driven illustration tinted by the variant, or copy only.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-[var(--space-6)]">
          <div className={regionClass}>
            <Empty aria-labelledby="es-m1-title" variant="no-results">
              <EmptyMedia variant="icon">{searchIcon}</EmptyMedia>
              <EmptyTitle id="es-m1-title">Icon chip</EmptyTitle>
              <EmptyDescription>
                The default treatment — one glyph in a tinted circle.
              </EmptyDescription>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-m2-title" variant="first-use">
              <EmptyMedia variant="default">{illustration}</EmptyMedia>
              <EmptyTitle id="es-m2-title">Illustration</EmptyTitle>
              <EmptyDescription>
                Author-provided art — size-free slot, tinted by the variant.
              </EmptyDescription>
              <EmptyContent>
                <Button size="sm">Get started</Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-m3-title" variant="no-data">
              <EmptyTitle id="es-m3-title">Copy only</EmptyTitle>
              <EmptyDescription>
                No media at all — a title and a sentence are a complete empty state.
              </EmptyDescription>
            </Empty>
          </div>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="actions-heading">
        <h2 className="mb-2 text-xl" id="actions-heading">
          Actions — composition and states
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Controls are unmodified Button components, so focus, disabled, and loading come for free —
          mirrored statically via data-state on neutral scenarios, since none of these states is an
          error.
        </p>

        <div className="grid gap-[var(--space-6)]">
          <div className={regionClass}>
            <Empty aria-labelledby="es-a1-title" variant="first-use">
              <EmptyTitle id="es-a1-title">Primary only</EmptyTitle>
              <EmptyDescription>One clear next step — the strongest recipe.</EmptyDescription>
              <EmptyContent>
                <span className={actionLabelClass}>Action</span>
                <Button>Create company</Button>
                <span className={actionLabelClass}>Focus</span>
                <Button data-state="focus-visible" tabIndex={-1}>
                  Create company
                </Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-a2-title" variant="no-results">
              <EmptyTitle id="es-a2-title">Primary + secondary</EmptyTitle>
              <EmptyDescription>A main path with a quieter alternative beside it.</EmptyDescription>
              <EmptyContent>
                <span className={actionLabelClass}>Action</span>
                <Button>Search again</Button>
                <Button variant="secondary">Browse all</Button>
                <span className={actionLabelClass}>Focus</span>
                <Button data-state="focus-visible" tabIndex={-1} variant="secondary">
                  Browse all
                </Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-a3-title" variant="no-data">
              <EmptyTitle id="es-a3-title">Primary + standalone link</EmptyTitle>
              <EmptyDescription>Navigation pairs naturally with an action.</EmptyDescription>
              <EmptyContent>
                <span className={actionLabelClass}>Action</span>
                <Button>Upload documents</Button>
                <Button variant="link">Document guide</Button>
                <span className={actionLabelClass}>Focus</span>
                <Button data-state="focus-visible" tabIndex={-1} variant="link">
                  Document guide
                </Button>
              </EmptyContent>
            </Empty>
          </div>

          <div className={regionClass}>
            <Empty aria-labelledby="es-a4-title" variant="no-results">
              <EmptyTitle id="es-a4-title">Disabled and loading</EmptyTitle>
              <EmptyDescription>
                States belong to the composed Button — nothing here is restyled, and a neutral
                scenario carries them because neither state is an error.
              </EmptyDescription>
              <EmptyContent>
                <span className={actionLabelClass}>Disabled</span>
                <Button disabled>Retry</Button>
                <span className={actionLabelClass}>Loading</span>
                <Button loading>Retrying</Button>
              </EmptyContent>
            </Empty>
          </div>
        </div>
      </section>

      <section className="py-8" aria-labelledby="context-heading">
        <h2 className="mb-2 text-xl" id="context-heading">
          In context — inside a card region
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The same component dropped into a real surface: the 480px measure centers itself with
          margin-inline auto whatever the region’s width, and block padding relaxes to --space-8
          under 768px.
        </p>

        <Card>
          <CardHeader>
            <CardTitle>Job postings</CardTitle>
          </CardHeader>
          <CardContent>
            <Empty aria-labelledby="es-ctx-title" variant="first-use">
              <EmptyMedia variant="icon">{briefcaseIcon}</EmptyMedia>
              <EmptyTitle id="es-ctx-title">No postings yet</EmptyTitle>
              <EmptyDescription>
                Publish the first opening for this company and it becomes searchable by matching
                tenants.
              </EmptyDescription>
              <EmptyContent>
                <Button>Create posting</Button>
                <Button variant="ghost">Preview template</Button>
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
        <p className="mt-6 max-w-2xl text-caption-foreground text-xs">
          Content-driven by design: the component contributes structure, rhythm, and the variant
          color system — copy, media, and actions all come from the caller, and it declares no
          transitions of its own.
        </p>
      </section>
    </main>
  )
}
