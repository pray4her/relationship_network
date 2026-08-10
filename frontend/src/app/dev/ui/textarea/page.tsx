import { Textarea } from "@/components/ui/textarea"

/**
 * Textarea 预览页 —— 对应 showcase/textarea.html:
 * 完整状态矩阵(8 个显式状态)+ 尺寸 + token map。
 * 状态经 data-[state=*] 镜像静态渲染(见 ui/textarea.tsx 注释);
 * label / helper / count / 校验消息属于 FormField 的 chrome,此处用页面脚手架代替。
 */

const cardClass = "rounded-[var(--radius-lg)] border border-border bg-card p-6"
const cardNameClass = "mb-4 block text-primary text-xs uppercase"
const labelClass = "mb-2 block text-sm font-medium"
const helpClass = "mt-2 text-muted-foreground text-sm"

export default function TextareaPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Textarea</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Eight explicit states using the same semantic field language as Input. Validation, count,
          resize, disabled, and read-only behavior stay native and accessible.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          Complete state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Hover and focus use deterministic data-state mirrors while the same native selectors
          remain active. The lower-right native handle demonstrates the default vertical resize
          affordance.
        </p>

        <div className="grid max-w-[720px] gap-4">
          <article className={cardClass}>
            <span className={cardNameClass}>Default · placeholder · resize</span>
            <label className={labelClass} htmlFor="textarea-default">
              Internal note
            </label>
            <Textarea
              aria-describedby="textarea-default-help"
              id="textarea-default"
              placeholder="Add context for the team…"
              rows={5}
            />
            <p className={helpClass} id="textarea-default-help">
              Optional context. Resize vertically when more room is useful.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Hover</span>
            <label className={labelClass} htmlFor="textarea-hover">
              Role summary
            </label>
            <Textarea
              aria-describedby="textarea-hover-help"
              data-state="hover"
              id="textarea-hover"
              placeholder="Summarize the opportunity…"
              rows={5}
            />
            <p className={helpClass} id="textarea-hover-help">
              Hover strengthens the shared Input-family border.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Focus-visible</span>
            <div className="mb-2 flex items-baseline justify-between gap-4">
              <label className="text-sm font-medium" htmlFor="textarea-focus">
                Interview feedback
              </label>
              <span aria-live="polite" className="text-caption-foreground text-xs">
                59 / 280
              </span>
            </div>
            <Textarea
              aria-describedby="textarea-focus-help"
              data-state="focus-visible"
              defaultValue="Strong systems thinking and clear communication throughout."
              id="textarea-focus"
              maxLength={280}
              rows={5}
            />
            <p className={helpClass} id="textarea-focus-help">
              Focus matches Input through the shared primary border and semantic focus ring.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Filled · character count</span>
            <div className="mb-2 flex items-baseline justify-between gap-4">
              <label className="text-sm font-medium" htmlFor="textarea-filled">
                Candidate pitch
              </label>
              <span aria-live="polite" className="text-caption-foreground text-xs">
                121 / 280
              </span>
            </div>
            <Textarea
              aria-describedby="textarea-filled-help"
              defaultValue="Platform engineer experienced in reliable data systems, careful migrations, and small senior teams. Open to remote roles."
              id="textarea-filled"
              maxLength={280}
              rows={5}
            />
            <p className={helpClass} id="textarea-filled-help">
              Entered text uses the primary foreground; the polite-live count occupies the header
              slot.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Error</span>
            <label className={labelClass} htmlFor="textarea-error">
              Offer terms{" "}
              <span aria-hidden="true" className="text-destructive">
                *
              </span>
            </label>
            <Textarea
              aria-describedby="textarea-error-help textarea-error-message"
              aria-invalid="true"
              defaultValue="TBD"
              id="textarea-error"
              required
              rows={5}
            />
            <p className={helpClass} id="textarea-error-help">
              These terms are visible to the candidate.
            </p>
            <p className="mt-2 text-destructive text-sm" id="textarea-error-message" role="alert">
              Add complete offer terms before sending.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Success</span>
            <label className={labelClass} htmlFor="textarea-success">
              Candidate summary
            </label>
            <Textarea
              aria-describedby="textarea-success-message"
              data-state="success"
              defaultValue="Senior platform engineer with verified availability and location preferences."
              id="textarea-success"
              rows={5}
            />
            <p className="mt-2 text-sm text-success" id="textarea-success-message" role="status">
              <span aria-hidden="true">✓</span> Summary is ready to publish.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Disabled</span>
            <label className={labelClass} htmlFor="textarea-disabled">
              Suspension note
            </label>
            <Textarea
              aria-describedby="textarea-disabled-help"
              defaultValue="Workspace suspended — contact the platform administrator."
              disabled
              id="textarea-disabled"
              rows={5}
            />
            <p className={helpClass} id="textarea-disabled-help">
              Disabled treatment uses the system opacity and removes resizing.
            </p>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Read-only</span>
            <label className={labelClass} htmlFor="textarea-readonly">
              Audit summary
            </label>
            <Textarea
              aria-describedby="textarea-readonly-help"
              className="resize-none"
              defaultValue="12 ledger entries · 3 invitations · 1 suspension."
              id="textarea-readonly"
              readOnly
              rows={5}
            />
            <p className={helpClass} id="textarea-readonly-help">
              Read-only content stays focusable and copyable on the shared muted surface.
            </p>
          </article>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="sizes-heading">
        <h2 className="mb-2 text-xl" id="sizes-heading">
          Sizes
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Sizes pair with rows (sm=3, md=5, lg=8); min-height tokens only guard against resize
          shrinking below the size&apos;s intent.
        </p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className={`grid content-start gap-4 ${cardClass}`}>
            <h3 className="text-base font-medium">sm · rows=3</h3>
            <Textarea placeholder="Compact note…" rows={3} size="sm" />
            <p className="text-muted-foreground text-xs">
              --textarea-min-height-sm + body-sm typography
            </p>
          </article>
          <article className={`grid content-start gap-4 ${cardClass}`}>
            <h3 className="text-base font-medium">md · rows=5 (default)</h3>
            <Textarea placeholder="Standard multi-line field…" rows={5} size="md" />
            <p className="text-muted-foreground text-xs">
              --textarea-min-height-md + body-md typography
            </p>
          </article>
          <article className={`grid content-start gap-4 ${cardClass}`}>
            <h3 className="text-base font-medium">lg · rows=8</h3>
            <Textarea placeholder="Long-form entry…" rows={8} size="lg" />
            <p className="text-muted-foreground text-xs">
              --textarea-min-height-lg + body-md typography
            </p>
          </article>
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-2 text-xl" id="mapping-heading">
          Token map
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4">
          <article className={cardClass}>
            <p className="text-sm font-medium">Surface and border</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--background / --muted</code>
              <code>--input / --border-strong</code>
              <code>--border-width / --radius-md</code>
            </p>
          </article>
          <article className={cardClass}>
            <p className="text-sm font-medium">Focus and error</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--primary / --ring-focus</code>
              <code>--ring-width</code>
              <code>--destructive / --ring-destructive</code>
            </p>
          </article>
          <article className={cardClass}>
            <p className="text-sm font-medium">Dimensions and spacing</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--textarea-min-height-md</code>
              <code>--input-padding-block / --input-padding-inline</code>
            </p>
          </article>
          <article className={cardClass}>
            <p className="text-sm font-medium">Text, disabled, motion</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--foreground / --caption-foreground</code>
              <code>--opacity-disabled</code>
              <code>--duration-fast / --ease-standard</code>
            </p>
          </article>
        </div>
      </section>
    </main>
  )
}
