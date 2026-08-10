import { Separator } from "@/components/ui/separator"

/**
 * Separator 预览页 —— 对应 showcase/separator.html:
 * style × orientation 矩阵 + surface contexts + token map。
 * Separator 为非交互元素,规格无状态镜像;装饰性样品透传 aria-hidden。
 */
const styles = [
  {
    variant: "subtle",
    label: "Subtle",
    tokens: ["--border-soft", "--border-width"],
    horizontal: ["Related supporting content", "Low-emphasis continuation"],
    vertical: ["Metadata", "Supporting detail"],
    decorative: true,
  },
  {
    variant: "default",
    label: "Default",
    tokens: ["--border", "--border-width"],
    horizontal: ["Independent content group", "Next content group"],
    vertical: ["Primary group", "Secondary group"],
    decorative: false,
  },
  {
    variant: "strong",
    label: "Strong",
    tokens: ["--border-strong", "--border-width-strong"],
    horizontal: ["Major content region", "Distinct major region"],
    vertical: ["Safe actions", "Critical actions"],
    decorative: false,
  },
] as const

const thClass = "border-border-soft border-r border-b bg-surface-soft p-4 text-left align-top"
const tdClass = "border-border-soft border-r border-b p-4 align-top"
const rowHeadClass = `${tdClass} bg-card`

export default function SeparatorPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Separator</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          The complete style and orientation matrix. Hierarchy comes from semantic border color and
          thickness tokens; spacing is identical across styles for a stable content rhythm.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Applicable state matrix — style × orientation
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          All six supported combinations are shown at the same scale for direct contrast and
          hierarchy comparison.
        </p>

        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-popover shadow-subtle">
          <table className="w-full min-w-[560px] border-collapse">
            <thead>
              <tr>
                <th className={thClass} scope="col">
                  Style
                </th>
                <th className={thClass} scope="col">
                  Horizontal
                </th>
                <th className={thClass} scope="col">
                  Vertical
                </th>
              </tr>
            </thead>
            <tbody>
              {styles.map((style) => (
                <tr key={style.variant}>
                  <th className={rowHeadClass} scope="row">
                    <span className="block text-base font-medium">{style.label}</span>
                    <span className="mt-3 grid gap-1 text-muted-foreground text-xs">
                      {style.tokens.map((token) => (
                        <code className="font-mono" key={token}>
                          {token}
                        </code>
                      ))}
                    </span>
                  </th>
                  <td className={tdClass}>
                    <div className="py-2">
                      <p className="m-0 text-sm">{style.horizontal[0]}</p>
                      <Separator variant={style.variant} />
                      <p className="m-0 text-sm">{style.horizontal[1]}</p>
                    </div>
                  </td>
                  <td className={tdClass}>
                    <div className="flex min-h-[var(--control-height-lg)] items-stretch text-foreground-body text-sm">
                      <span className="flex items-center">{style.vertical[0]}</span>
                      <Separator
                        aria-hidden={style.decorative || undefined}
                        orientation="vertical"
                        variant={style.variant}
                      />
                      <span className="flex items-center">{style.vertical[1]}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="contexts-heading">
        <h2 className="mb-2 text-xl" id="contexts-heading">
          Surface contexts
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Context behavior follows semantic capability in the current Token set.
        </p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="m-0 text-base font-medium">Disabled — not applicable</h3>
            <p className="m-0 mt-2 text-muted-foreground text-sm">
              A Separator is structural and non-interactive, so it has no disabled state.{" "}
              <code className="font-mono">--opacity-disabled</code> remains reserved for disabled
              controls and is not applied here.
            </p>
          </article>
          <article className="rounded-[var(--radius-lg)] border border-[color:var(--surface-dark-elevated)] bg-surface-dark p-6 text-on-dark">
            <h3 className="m-0 text-base font-medium">Inverse — Token gap</h3>
            <p className="m-0 mt-2 text-on-dark-soft text-sm">
              No inverse border or separator token exists. Text roles{" "}
              <code className="font-mono">--on-dark</code> and{" "}
              <code className="font-mono">--on-dark-soft</code> are not repurposed as line colors,
              so an inverse Separator is intentionally not rendered.
            </p>
          </article>
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-2 text-xl" id="mapping-heading">
          Token map
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          No raw color, thickness, opacity, or spacing values are used by the component.
        </p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-3">
          <article className="rounded-[var(--radius-md)] border border-border-soft bg-surface-soft p-4">
            <p className="m-0 text-sm font-medium">Color</p>
            <p className="m-0 text-muted-foreground text-xs">
              <code className="font-mono">--border-soft</code> ·{" "}
              <code className="font-mono">--border</code> ·{" "}
              <code className="font-mono">--border-strong</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-md)] border border-border-soft bg-surface-soft p-4">
            <p className="m-0 text-sm font-medium">Thickness</p>
            <p className="m-0 text-muted-foreground text-xs">
              <code className="font-mono">--border-width</code> ·{" "}
              <code className="font-mono">--border-width-strong</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-md)] border border-border-soft bg-surface-soft p-4">
            <p className="m-0 text-sm font-medium">Surrounding spacing</p>
            <p className="m-0 text-muted-foreground text-xs">
              <code className="font-mono">--space-4</code> on the orientation axis
            </p>
          </article>
          <article className="rounded-[var(--radius-md)] border border-border-soft bg-surface-soft p-4">
            <p className="m-0 text-sm font-medium">Opacity</p>
            <p className="m-0 text-muted-foreground text-xs">
              No opacity applied; semantic border colors define contrast
            </p>
          </article>
        </div>
      </section>
    </main>
  )
}
