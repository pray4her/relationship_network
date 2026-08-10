import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"

/**
 * Spinner 预览页 —— 对应 showcase/spinner.html:
 * 尺寸 × variant 矩阵、组合上下文、Button loading 组合、reduced-motion 冻结、加载层级。
 * reduced-motion 冻结经 data-state="reduced" 镜像静态渲染(见 ui/spinner.tsx 注释)。
 */
const sizes = [
  { value: "xs", caption: "xs · 12px" },
  { value: "sm", caption: "sm · 16px" },
  { value: "md", caption: "md · 18px" },
  { value: "lg", caption: "lg · 24px" },
] as const

const matrixClass =
  "grid grid-cols-[minmax(80px,auto)_repeat(4,1fr)] items-center justify-items-center gap-6 p-6"

const captionClass = "justify-self-start text-xs"
const regionClass = "rounded-[var(--radius-lg)] border border-border bg-background p-6"

export default function SpinnerPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Spinner</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Indeterminate loader: a foreground arc rotating over a background track, every stroke,
          size, opacity, duration, and easing a tokens.css reference.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Loading state matrix — all sizes × variants
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          xs / sm / md / lg ride the icon-size ladder; the stroke holds at --space-0-5 through md
          and steps one micro rung up (--space-0-75) at lg. Inverse rides a --surface-dark band —
          the only surface its tokens support.
        </p>

        <div className={regionClass}>
          <div className={matrixClass}>
            <span />
            {sizes.map((size) => (
              <span className="text-xs" key={size.value}>
                {size.caption}
              </span>
            ))}

            <span className={captionClass}>default</span>
            {sizes.map((size) => (
              <Spinner aria-hidden="true" key={size.value} size={size.value} />
            ))}

            <span className={captionClass}>primary</span>
            {sizes.map((size) => (
              <Spinner aria-hidden="true" key={size.value} size={size.value} variant="primary" />
            ))}
          </div>

          <div className={`${matrixClass} rounded-[var(--radius-md)] bg-surface-dark`}>
            <span className={`${captionClass} text-on-dark-soft`}>inverse</span>
            {sizes.map((size) => (
              <Spinner aria-hidden="true" key={size.value} size={size.value} variant="inverse" />
            ))}
          </div>
        </div>
        <p className="mt-6 max-w-xl text-muted-foreground text-xs">
          Stroke pairs: default arc --foreground on track --border; primary arc --primary on track
          --primary-disabled; inverse arc --on-dark on track --surface-dark-elevated. Both strokes
          are opaque token colors — no raw alpha.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="context-heading">
        <h2 className="mb-2 text-xl" id="context-heading">
          Contexts — only, labelled, inline
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Ring only: role=&quot;status&quot; with an author-supplied aria-label when it communicates
          state, or aria-hidden when decorative. Ring plus label: the visible text is the accessible
          label and the wrapper is the live region. Inline loader: an xs ring dropped into running
          text at the copy&apos;s baseline.
        </p>

        <div className="grid gap-6">
          <div className={regionClass}>
            <div className="flex flex-wrap items-center gap-8">
              <Spinner aria-label="Loading members" />
              <span className="text-xs">ring only · role=&quot;status&quot; + aria-label</span>

              <Spinner label="Matching talent…" variant="primary" />
              <span className="text-xs">ring + visible label · live region</span>

              <span className="text-sm">
                Syncing index <Spinner aria-hidden="true" size="xs" />
              </span>
              <span className="text-xs">inline loader · aria-hidden beside text</span>
            </div>
          </div>

          <div className="rounded-[var(--radius-lg)] bg-surface-dark p-6">
            <div className="flex flex-wrap items-center gap-8">
              <Spinner label="Uploading documents…" variant="inverse" />
              <span className="text-on-dark-soft text-xs">inverse + label on --surface-dark</span>
            </div>
          </div>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="button-heading">
        <h2 className="mb-2 text-xl" id="button-heading">
          Button loading state
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Two recipes, one hierarchy: the Button&apos;s native loading contract (its own ring, same
          token recipe), and this component composed in the icon slot, aria-hidden, with the button
          text as the accessible name. Inverse on filled buttons, default on quiet ones; sm matches
          the native footprint, xs fits the sm button.
        </p>

        <div className={regionClass}>
          <div className="flex flex-wrap items-center gap-4">
            <Button loading>Saving…</Button>
            <Button aria-busy="true">
              <Spinner aria-hidden="true" size="sm" variant="inverse" />
              Saving…
            </Button>
            <Button aria-busy="true" variant="secondary">
              <Spinner aria-hidden="true" size="sm" />
              Loading…
            </Button>
            <Button aria-busy="true" variant="ghost">
              <Spinner aria-hidden="true" size="sm" />
              Refreshing
            </Button>
            <Button aria-busy="true" size="sm">
              <Spinner aria-hidden="true" size="xs" variant="inverse" />
              Saving…
            </Button>
            <Button disabled variant="secondary">
              <Spinner aria-hidden="true" size="sm" />
              Unavailable
            </Button>
          </div>
        </div>
        <p className="mt-6 max-w-xl text-muted-foreground text-xs">
          Busy ≠ unavailable: loading keeps full opacity while a plain disabled drops to
          --opacity-disabled — the only opacity in the system, and it belongs to Button, not to the
          ring.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="motion-heading">
        <h2 className="mb-2 text-xl" id="motion-heading">
          Reduced-motion treatment
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Rotation is --duration-slow linear infinite. Under prefers-reduced-motion: reduce the
          animation is removed and the ring holds as a static three-quarter arc; the label keeps
          carrying the state. The data-state=&quot;reduced&quot; twin renders that freeze
          statically.
        </p>
        <div className={regionClass}>
          <div className="flex flex-wrap items-center gap-8">
            <Spinner label="Building your match report…" size="lg" variant="primary" />
            <span className="text-xs">live · --duration-slow linear</span>

            <Spinner
              data-state="reduced"
              label="Building your match report…"
              size="lg"
              variant="primary"
            />
            <span className="text-xs">reduced · static arc, label carries state</span>
          </div>
        </div>
      </section>

      <section className="py-8" aria-labelledby="hierarchy-heading">
        <h2 className="mb-2 text-xl" id="hierarchy-heading">
          Loading hierarchy — against the system
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Skeleton owns whole regions, the labelled spinner owns a panel or a request, Button
          loading owns a single control, and the inline xs ring owns a phrase.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-6">
          <div className={`${regionClass} grid content-start justify-items-start gap-4`}>
            <span className="text-xs">block · Skeleton</span>
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
          </div>

          <div className={`${regionClass} grid content-start justify-items-start gap-4`}>
            <span className="text-xs">region · Spinner + label</span>
            <Spinner label="Loading roster…" size="lg" variant="primary" />
          </div>

          <div className={`${regionClass} grid content-start justify-items-start gap-4`}>
            <span className="text-xs">control · Button loading</span>
            <Button loading>Saving…</Button>
          </div>

          <div className={`${regionClass} grid content-start justify-items-start gap-4`}>
            <span className="text-xs">text · inline loader</span>
            <span className="text-sm">
              Index refreshed <Spinner aria-hidden="true" size="xs" />
            </span>
          </div>
        </div>
      </section>
    </main>
  )
}
