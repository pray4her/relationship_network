import { Button } from "@/components/ui/button"

/**
 * Button 预览页 —— 对应 showcase/button.html:
 * 4 variant × 3 size × 6 state 交互矩阵 + 内容配置。
 * 状态经 data-[state=*] 镜像静态渲染(见 ui/button.tsx 注释)。
 */
const variants = ["default", "secondary", "ghost", "destructive"] as const
const sizes = ["sm", "default", "lg"] as const
const states = [
  { label: "Default", props: {} },
  { label: "Hover", props: { "data-state": "hover" } },
  { label: "Active", props: { "data-state": "active" } },
  { label: "Focus-visible", props: { "data-state": "focus-visible" } },
  { label: "Disabled", props: { disabled: true } },
  { label: "Loading", props: { loading: true } },
] as const

const plusIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <path d="M8 3v10M3 8h10" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const arrowIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <path
      d="M3 8h10M9 4l4 4-4 4"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const thClass = "border-border-soft border-r border-b bg-surface-soft p-3 text-left align-middle"
const tdClass = "border-border-soft border-r border-b p-3 align-middle"
const rowHeadClass = `${tdClass} bg-card`

export default function ButtonPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Button</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          The complete 4 variant × 3 size × 6 state interaction matrix, rendered with the React
          implementation.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Full interaction state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          All combinations rendered; states mirrored via data-state attributes.
        </p>

        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-popover shadow-subtle">
          <table className="w-full min-w-[560px] border-collapse">
            <thead>
              <tr>
                <th className={thClass} scope="col">
                  Variant / size
                </th>
                {states.map((state) => (
                  <th className={thClass} key={state.label} scope="col">
                    {state.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {variants.map((variant) =>
                sizes.map((size, sizeIndex) => (
                  <tr key={`${variant}-${size}`}>
                    <th className={rowHeadClass} scope="row">
                      {variant} / {size === "default" ? "md" : size}
                    </th>
                    {states.map((state) => (
                      <td className={tdClass} key={state.label}>
                        <Button size={size} variant={variant} {...state.props}>
                          {sizeIndex === 0 ? "Create posting" : "Button"}
                        </Button>
                      </td>
                    ))}
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="composition-heading">
        <h2 className="mb-2 text-xl" id="composition-heading">
          Content configurations
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Decorative icons inherit the button foreground and use the shared icon size, stroke, and
          gap tokens.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Text only</h3>
            <Button>Create posting</Button>
            <p className="text-muted-foreground text-xs">Minimal content contract</p>
          </article>

          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Leading icon + text</h3>
            <Button variant="secondary">
              {plusIcon}
              Add member
            </Button>
            <p className="text-muted-foreground text-xs">Icon precedes the visible label</p>
          </article>

          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Text + trailing icon</h3>
            <Button variant="ghost">
              View details
              {arrowIcon}
            </Button>
            <p className="text-muted-foreground text-xs">Icon follows the visible label</p>
          </article>
        </div>
      </section>

      <section className="py-8" aria-labelledby="aliases-heading">
        <h2 className="mb-2 text-xl" id="aliases-heading">
          API aliases
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Existing API names mapped to the nearest spec: outline→secondary, xs→sm, icon sizes→
          IconButton spec (radius-full).
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <Button variant="outline">Outline (=secondary)</Button>
          <Button size="xs">XS (=sm)</Button>
          <Button size="icon" variant="secondary">
            {plusIcon}
          </Button>
          <Button size="icon-sm" variant="ghost">
            {plusIcon}
          </Button>
          <Button size="icon-lg" variant="default">
            {plusIcon}
          </Button>
          <Button variant="link">Standalone link</Button>
        </div>
      </section>
    </main>
  )
}
