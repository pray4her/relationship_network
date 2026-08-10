import { Skeleton } from "@/components/ui/skeleton"

/**
 * Skeleton 预览页 —— 对应 showcase/skeleton.html:
 * 6 context × 3 motion-treatment 状态矩阵 + 形状组合 / 文本块 / 头像+文本 / 卡片 / 表格行示例。
 * 规格的 .skeleton--static / .skeleton--reduced-motion 预览态经 data-[state=*] 镜像静态渲染
 * (见 ui/skeleton.tsx 注释);尺寸覆盖全部走镜像内容的 token 任意值(对应规格 --_w/--_h/--_r)。
 */
const modes = [
  { label: "Static", props: { "data-state": "static" } },
  { label: "Animated", props: {} },
  { label: "Reduced-motion", props: { "data-state": "reduced-motion" } },
] as const

type ModeProps = { "data-state"?: string }

const contexts = [
  "single text line",
  "multi-line text",
  "avatar",
  "avatar + text",
  "card",
  "table row",
] as const

/** 对应 showcase 状态矩阵脚本的 skeletonPattern:每个 context 的典型加载形态。 */
function MatrixPattern({
  context,
  modeProps,
}: {
  context: (typeof contexts)[number]
  modeProps: ModeProps
}) {
  switch (context) {
    case "single text line":
      return <Skeleton className="w-[calc(100%_-_var(--space-8))]" variant="text" {...modeProps} />
    case "multi-line text":
      return (
        <div className="grid gap-[var(--space-2)]">
          <Skeleton variant="text" {...modeProps} />
          <Skeleton className="w-[calc(100%_-_var(--space-8))]" variant="text" {...modeProps} />
          <Skeleton className="w-[calc(100%_-_var(--space-16))]" variant="text" {...modeProps} />
        </div>
      )
    case "avatar":
      return <Skeleton variant="circle" {...modeProps} />
    case "avatar + text":
      return (
        <div className="flex items-center gap-[var(--space-3)]">
          <Skeleton variant="circle" {...modeProps} />
          <div className="grid min-w-0 flex-1 gap-[var(--space-2)]">
            <Skeleton variant="text" {...modeProps} />
            <Skeleton className="w-[calc(100%_-_var(--space-12))]" variant="text" {...modeProps} />
          </div>
        </div>
      )
    case "card":
      return (
        <div className="grid gap-[var(--space-2)] rounded-[var(--radius-lg)] border border-border p-[var(--space-4)]">
          <Skeleton className="h-[var(--space-12)]" {...modeProps} />
          <Skeleton variant="text" {...modeProps} />
          <Skeleton className="w-[calc(100%_-_var(--space-8))]" variant="text" {...modeProps} />
        </div>
      )
    case "table row":
      return (
        <div className="flex items-center gap-[var(--space-3)] border-border-soft border-y py-[var(--space-3)]">
          <Skeleton className="size-[var(--avatar-size-xs)]" variant="circle" {...modeProps} />
          <div className="grid min-w-0 flex-1 gap-[var(--space-2)]">
            <Skeleton variant="text" {...modeProps} />
          </div>
          <Skeleton className="w-[var(--space-8)]" variant="text" {...modeProps} />
        </div>
      )
  }
}

const matrixCellClass =
  "grid min-w-0 content-center gap-[var(--space-2)] border-border-soft border-r border-b p-[var(--space-4)]"

const tableRows = [
  { name: "w-[var(--space-24)]", role: "w-[var(--space-16)]" },
  {
    name: "w-[calc(var(--space-24)_+_var(--space-6))]",
    role: "w-[calc(var(--space-16)_+_var(--space-8))]",
  },
  {
    name: "w-[calc(var(--space-24)_-_var(--space-4))]",
    role: "w-[calc(var(--space-16)_-_var(--space-4))]",
  },
] as const

const thClass =
  "border-border border-b bg-surface-soft px-[var(--space-6)] py-[var(--space-4)] text-left font-medium text-muted-foreground text-xs uppercase tracking-[var(--text-caption-up--letter-spacing)]"
const tdClass = "border-border-soft border-b px-[var(--space-6)] py-[var(--space-3)] align-middle"

export default function SkeletonPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Skeleton</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          A loading placeholder that mirrors the geometry of the content it replaces. Sizes are
          composed from the tokens of whatever is being mirrored — never encoded. Every skeleton is
          aria-hidden; the surrounding region carries aria-busy and names what is loading.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Full loading state matrix — context × motion treatment
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Animated is the default loading treatment. Static suppresses the sheen intentionally;
          reduced-motion mirrors the system media-query result via data-state attributes.
        </p>

        <div className="grid grid-cols-[8rem_repeat(3,minmax(0,1fr))] overflow-x-auto rounded-[var(--radius-lg)] border border-border">
          <div className={`${matrixCellClass} bg-surface-soft`}>
            <span className="text-muted-foreground text-xs uppercase">Context</span>
          </div>
          {modes.map((mode) => (
            <div className={`${matrixCellClass} bg-surface-soft`} key={mode.label}>
              <span className="text-muted-foreground text-xs uppercase">{mode.label}</span>
            </div>
          ))}
          {contexts.map((context) => (
            <div className="contents" key={context}>
              <div className={`${matrixCellClass} bg-card`}>
                <strong className="text-sm">{context}</strong>
              </div>
              {modes.map((mode) => (
                <div className={matrixCellClass} key={mode.label}>
                  <MatrixPattern context={context} modeProps={mode.props} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="shapes-heading">
        <h2 className="mb-2 text-xl" id="shapes-heading">
          Shapes &amp; composable sizes
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Three shapes — rectangle (control-height block), text (the body-md line box), circle (the
          Avatar scale) — every override composed inline from the mirrored content's own tokens
          instead of a hardcoded ladder.
        </p>
        <section
          aria-busy="true"
          aria-label="Loading shape specimens"
          className="grid max-w-xl gap-[var(--space-3)]"
        >
          <Skeleton />
          <Skeleton className="h-[var(--space-24)] rounded-[var(--radius-lg)]" />
          <Skeleton variant="text" />
          <Skeleton
            className="h-[calc(var(--text-title-md)*var(--text-title-md--line-height))]"
            variant="text"
          />
          <Skeleton
            className="h-[calc(var(--text-caption)*var(--text-caption--line-height))] w-[calc(100%_-_var(--space-24))]"
            variant="text"
          />
          <div className="flex flex-wrap items-center gap-[var(--space-4)]">
            <Skeleton variant="circle" />
            <Skeleton className="size-[var(--avatar-size-lg)]" variant="circle" />
            <Skeleton className="size-[var(--icon-button-size)]" variant="circle" />
          </div>
        </section>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="textblock-heading">
        <h2 className="mb-2 text-xl" id="textblock-heading">
          Example — text block
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Line widths step down by spacing tokens the way real paragraphs rag; the lead line
          composes the title-lg line box.
        </p>
        <section
          aria-busy="true"
          aria-label="Loading article summary"
          className="grid max-w-xl gap-[var(--space-3)]"
        >
          <Skeleton
            className="h-[calc(var(--text-title-lg)*var(--text-title-lg--line-height))] w-[calc(100%_-_var(--space-16))]"
            variant="text"
          />
          <Skeleton variant="text" />
          <Skeleton variant="text" />
          <Skeleton className="w-[calc(100%_-_var(--space-24))]" variant="text" />
        </section>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="avatar-heading">
        <h2 className="mb-2 text-xl" id="avatar-heading">
          Example — avatar + text
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The disc is the circle shape at its Avatar-scale default; the two lines compose the
          body-md and body-sm line boxes — the exact pair a loaded member row renders.
        </p>
        <section
          aria-busy="true"
          aria-label="Loading member"
          className="flex max-w-xl items-start gap-[var(--space-4)]"
        >
          <Skeleton variant="circle" />
          <div className="grid min-w-0 flex-1 gap-[var(--space-2)]">
            <Skeleton className="w-[calc(100%_-_var(--space-16))]" variant="text" />
            <Skeleton
              className="h-[calc(var(--text-body-sm)*var(--text-body-sm--line-height))] w-[calc(100%_-_var(--space-24))]"
              variant="text"
            />
          </div>
        </section>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="card-heading">
        <h2 className="mb-2 text-xl" id="card-heading">
          Example — card
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Real Card surfaces host the placeholders. On the cream card the surface is composed one
          step darker (surface-cream-strong) so the blocks keep their contrast; on canvas-backed
          surfaces the default card fill is used as-is.
        </p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <section
            aria-busy="true"
            aria-label="Loading company card"
            className="flex flex-col gap-[var(--space-4)] rounded-[var(--radius-lg)] border border-border bg-background p-[var(--space-8)]"
          >
            <div className="flex items-center gap-[var(--space-3)]">
              <Skeleton variant="circle" />
              <div className="grid min-w-0 flex-1 gap-[var(--space-2)]">
                <Skeleton
                  className="h-[calc(var(--text-title-md)*var(--text-title-md--line-height))] w-[calc(100%_-_var(--space-8))]"
                  variant="text"
                />
                <Skeleton
                  className="h-[calc(var(--text-body-sm)*var(--text-body-sm--line-height))] w-[calc(100%_-_var(--space-16))]"
                  variant="text"
                />
              </div>
            </div>
            <Skeleton className="h-[var(--space-24)] rounded-[var(--radius-md)]" />
            <div className="flex flex-wrap items-center gap-[var(--space-3)]">
              <Skeleton className="h-[var(--control-height)] w-[var(--space-24)] rounded-[var(--radius-md)]" />
              <Skeleton className="h-[var(--control-height)] w-[var(--space-24)] rounded-[var(--radius-md)]" />
            </div>
          </section>
          <section
            aria-busy="true"
            aria-label="Loading feature card"
            className="flex flex-col gap-[var(--space-4)] rounded-[var(--radius-lg)] border border-transparent bg-surface-cream-strong p-[var(--space-8)]"
          >
            <Skeleton className="size-[var(--icon-button-size)] rounded-[var(--radius-md)]" />
            <Skeleton
              className="h-[calc(var(--text-title-md)*var(--text-title-md--line-height))] w-[calc(100%_-_var(--space-12))]"
              variant="text"
            />
            <Skeleton variant="text" />
            <Skeleton className="w-[calc(100%_-_var(--space-16))]" variant="text" />
          </section>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="table-heading">
        <h2 className="mb-2 text-xl" id="table-heading">
          Example — table rows
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The real Table chrome (header band, dividers, radii) stays live while the body mirrors its
          cell types: xs avatar disc + name line, role line, end-aligned number, and a pill-radius
          badge block — every width a spacing-token composition.
        </p>
        <section
          aria-busy="true"
          aria-label="Loading candidate table"
          className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-background"
        >
          <table className="w-full min-w-[560px] border-collapse text-left text-foreground-body">
            <thead>
              <tr>
                <th className={thClass} scope="col">
                  Candidate
                </th>
                <th className={thClass} scope="col">
                  Role
                </th>
                <th className={`${thClass} text-right`} scope="col">
                  Match
                </th>
                <th className={thClass} scope="col">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row) => (
                <tr className="bg-background last:[&>td]:border-b-0" key={row.name}>
                  <td className={tdClass}>
                    <span className="inline-flex items-center gap-[var(--space-2)]">
                      <Skeleton className="size-[var(--avatar-size-xs)]" variant="circle" />
                      <Skeleton className={row.name} variant="text" />
                    </span>
                  </td>
                  <td className={tdClass}>
                    <Skeleton className={row.role} variant="text" />
                  </td>
                  <td className={tdClass}>
                    <Skeleton className="ms-auto w-[var(--space-8)]" variant="text" />
                  </td>
                  <td className={tdClass}>
                    <Skeleton className="h-[var(--space-6)] w-[var(--space-16)] rounded-[var(--radius-full)]" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </section>

      <section className="py-8" aria-labelledby="aria-heading">
        <h2 className="mb-2 text-xl" id="aria-heading">
          Assistive-technology contract
        </h2>
        <p className="max-w-xl text-foreground-body">
          Skeletons convey no information, so each one carries aria-hidden="true". The wrapper of
          every example on this page carries aria-busy="true" plus an aria-label naming the pending
          content — screen readers announce one loading region, not a wall of empty blocks. When
          content lands, the region drops aria-busy and the skeletons leave the DOM. Under
          prefers-reduced-motion the sweep band is removed and the static cream blocks remain as the
          placeholder.
        </p>
      </section>
    </main>
  )
}
