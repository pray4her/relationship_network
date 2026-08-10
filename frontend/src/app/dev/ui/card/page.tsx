import { Button } from "@/components/ui/button"
import {
  Card,
  CardActions,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardMedia,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"

/**
 * Card 预览页 —— 对应 showcase/card.html:
 * 5 variant 矩阵 + anatomy + 交互状态矩阵 + pattern B 组合。
 * 状态经 data-[state=*] 镜像静态渲染(见 ui/card.tsx 注释);
 * 整卡可交互样品经 render prop 把根节点渲染为 <a>/<button>(规格 pattern A)。
 */

type MatrixCardProps = {
  label: string
  variant?: "default" | "outlined" | "elevated" | "selected"
  interactive?: boolean
  state?: "hover" | "active" | "focus-visible" | "disabled"
  disabled?: boolean
  ariaPressed?: boolean
}

/** showcase 的 matrix-card:相同内容结构,只换表面 variant / 状态。 */
function MatrixCard({
  label,
  variant,
  interactive,
  state,
  disabled,
  ariaPressed,
}: MatrixCardProps) {
  return (
    <div className="grid gap-[var(--space-3)]">
      <span className="text-caption-foreground text-xs">{label}</span>
      <Card
        className="h-full"
        data-state={state}
        disabled={disabled || undefined}
        interactive={interactive}
        render={<button aria-pressed={ariaPressed || undefined} type="button" />}
        variant={variant}
      >
        <CardMedia
          aria-hidden="true"
          className="grid min-h-[var(--space-24)] place-items-center bg-surface-dark"
        >
          <span className="size-[var(--space-12)] rounded-full bg-primary" />
        </CardMedia>
        <CardHeader>
          <div>
            <CardTitle>Senior Backend Engineer</CardTitle>
            <CardDescription>Platform team · Remote · {label}</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <p>Own a high-impact hiring workflow and collaborate with a focused global team.</p>
        </CardContent>
        <CardActions className="mt-auto">
          {/* 整卡根已是 button,内部动作只能是 span;nativeButton=false 关闭 Base UI 的原生 button 校验 */}
          <Button nativeButton={false} render={<span />} size="sm">
            View role
          </Button>
          <Button nativeButton={false} render={<span />} size="sm" variant="secondary">
            Save
          </Button>
        </CardActions>
      </Card>
    </div>
  )
}

/** showcase 的 initials avatar(内容组合,非卡片样式)。 */
function InitialsAvatar({ initials, label }: { initials: string; label: string }) {
  return (
    <span
      aria-label={label}
      className="grid size-[var(--avatar-size-md)] shrink-0 place-items-center rounded-full bg-primary text-[length:var(--text-body-sm)] text-primary-foreground"
      role="img"
    >
      {initials}
    </span>
  )
}

const creamCoverImg =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 120'><rect width='320' height='120' fill='%23e8e0d2'/><circle cx='72' cy='60' r='34' fill='%23cc785c'/><rect x='140' y='34' width='130' height='52' rx='8' fill='%23181715'/></svg>"
const darkCoverImg =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 120'><rect width='320' height='120' fill='%23181715'/><circle cx='248' cy='44' r='26' fill='%23cc785c'/><rect x='32' y='72' width='150' height='16' rx='8' fill='%23f5f0e8'/></svg>"

const surfaceCells = [
  {
    variant: "default",
    caption: "default — --card fill, no border (feature-card recipe)",
    title: "Default",
    description: "Cream fill one step below the canvas",
    body: "The workhorse surface for feature and content groupings.",
  },
  {
    variant: "outlined",
    caption: "outlined — --background + --border hairline",
    title: "Outlined",
    description: "Canvas fill with a hairline border",
    body: "For dense lists where a filled card would feel heavy.",
  },
  {
    variant: "elevated",
    caption: "elevated — --background + --shadow-subtle (used rarely)",
    title: "Elevated",
    description: "The one sanctioned shadow",
    body: "Reserved for moments that must float above the canvas.",
  },
  {
    variant: "selected",
    caption: "selected — --selected-bg + --selected-border hairline",
    title: "Selected",
    description: "The emphasized-band token speaks",
    body: "Marks the chosen item in pickers and comparison grids.",
  },
] as const

const compactStates = [
  { label: "default", caption: "default" },
  { label: "hover", caption: "hover — lifts with --shadow-subtle", state: "hover" },
  { label: "active", caption: "active — pressed back to flat", state: "active" },
  {
    label: "focus-visible",
    caption: "focus-visible — shared --ring-focus recipe",
    state: "focus-visible",
  },
] as const

const captionClass = "text-caption-foreground text-xs"
const noteClass = "mt-4 max-w-xl text-muted-foreground text-sm"
const sectionClass = "border-border-soft border-b py-8"
const demoGridClass = "grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] items-start gap-6"
const stateGridClass = "grid grid-cols-1 gap-6 md:grid-cols-3"

function CompactCard({
  caption,
  state,
  variant,
  ariaCurrent,
  disabled,
}: {
  caption: string
  state?: "hover" | "active" | "focus-visible" | undefined
  variant?: "elevated" | "selected" | undefined
  ariaCurrent?: boolean
  disabled?: boolean
}) {
  return (
    <div className="grid gap-[var(--space-3)]">
      <span className={captionClass}>{caption}</span>
      {disabled ? (
        <Card data-state="disabled" disabled interactive render={<button type="button" />}>
          <CardTitle>Senior Backend Engineer</CardTitle>
          <CardDescription>Platform team · Remote</CardDescription>
        </Card>
      ) : (
        <Card
          aria-current={ariaCurrent || undefined}
          data-state={state}
          interactive
          render={<a href="#job-1" />}
          variant={variant}
        >
          <CardTitle>Senior Backend Engineer</CardTitle>
          <CardDescription>Platform team · Remote</CardDescription>
        </Card>
      )}
    </div>
  )
}

export default function CardPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Card</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          A composable surface container — five surface variants, optional parts, zero business
          content. Whole-card interactivity uses pattern A (the root IS the anchor, rendered via the
          render prop); cards with buttons use pattern B (inert root, interactivity lives in
          CardActions). States are mirrored via data-state attributes.
        </p>
      </header>

      <section className={sectionClass} aria-labelledby="variants-heading">
        <h2 className="mb-2 text-xl" id="variants-heading">
          Full variant matrix — identical content structure
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Every card carries the same media, title, description, body, and actions; only the
          documented surface variant changes.
        </p>
        <div className={stateGridClass}>
          <MatrixCard label="default" />
          <MatrixCard label="outlined" variant="outlined" />
          <MatrixCard label="elevated" variant="elevated" />
          <MatrixCard interactive label="interactive" />
          <MatrixCard label="selected" variant="selected" />
        </div>
        <p className={noteClass}>
          All variants keep a --border-width border (transparent when unused) so they stay the same
          outer size in a grid.
        </p>

        <h3 className="mt-8 mb-4 text-base font-medium">Surface-only comparison</h3>
        <div className={demoGridClass}>
          {surfaceCells.map((cell) => (
            <div className="grid gap-[var(--space-3)]" key={cell.variant}>
              <span className={captionClass}>{cell.caption}</span>
              <Card variant={cell.variant}>
                <CardTitle>{cell.title}</CardTitle>
                <CardDescription>{cell.description}</CardDescription>
                <CardContent>
                  <p>{cell.body}</p>
                </CardContent>
              </Card>
            </div>
          ))}
        </div>
      </section>

      <section className={sectionClass} aria-labelledby="anatomy-heading">
        <h2 className="mb-2 text-xl" id="anatomy-heading">
          Anatomy
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Parts are optional and order-free; the root column gap (--space-4) spaces whatever is
          present.
        </p>
        <div className={demoGridClass}>
          <div className="grid gap-[var(--space-3)]">
            <span className={captionClass}>
              full — media, header (avatar composed), title, description, body, footer, actions
              (Button composed)
            </span>
            <Card>
              <CardMedia>
                {/* biome-ignore lint/performance/noImgElement: data-URI 演示图,next/image 不优化内联资源 */}
                <img
                  alt="Abstract cover: coral circle and dark block on a cream field"
                  src={creamCoverImg}
                />
              </CardMedia>
              <CardHeader>
                <InitialsAvatar initials="GH" label="Grace Hopper" />
                <div>
                  <CardTitle>Every part at once</CardTitle>
                  <CardDescription>Media bleeds to the edges via the padding token</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <p>
                  Parts are optional and order-free; the root column gap spaces whatever is present.
                  The card knows nothing about profiles, plans, or posts.
                </p>
              </CardContent>
              <CardFooter>
                <CardActions>
                  <Button size="sm">Approve</Button>
                  <Button size="sm" variant="ghost">
                    Skip
                  </Button>
                </CardActions>
              </CardFooter>
            </Card>
          </div>
          <div className="grid gap-[var(--space-3)]">
            <span className={captionClass}>minimal — title + body only</span>
            <Card variant="outlined">
              <CardTitle>Quiet card</CardTitle>
              <CardContent>
                <p>
                  Two parts, same tokens. The body resets its first/last child margins so consumer
                  markup needs no spacing classes.
                </p>
                <p>Footer divider and actions stay home when not invited.</p>
              </CardContent>
            </Card>
            <span className={cn(captionClass, "mt-6")}>title + description pair, no body</span>
            <Card variant="outlined">
              <CardTitle>Label card</CardTitle>
              <CardDescription>
                A heading with a single muted line — the description token pair does the hierarchy.
              </CardDescription>
            </Card>
          </div>
        </div>
      </section>

      <section className={sectionClass} aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          Full interactive state matrix — identical content structure
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Pattern A roots rendered as buttons; states mirrored via data-state attributes.
        </p>
        <div className={stateGridClass}>
          <MatrixCard interactive label="default" />
          <MatrixCard interactive label="hover" state="hover" />
          <MatrixCard interactive label="active" state="active" />
          <MatrixCard interactive label="focus-visible" state="focus-visible" />
          <MatrixCard ariaPressed interactive label="selected" variant="selected" />
          <MatrixCard disabled interactive label="disabled" />
        </div>

        <h3 className="mt-8 mb-4 text-base font-medium">Compact state comparison</h3>
        <div className={demoGridClass}>
          {compactStates.map((item) => (
            <CompactCard
              caption={item.caption}
              key={item.label}
              state={"state" in item ? item.state : undefined}
            />
          ))}
          <CompactCard
            ariaCurrent
            caption="selected — compose the selected variant"
            variant="selected"
          />
          <CompactCard caption="disabled — --opacity-disabled, native disabled button" disabled />
          <CompactCard
            caption="elevated + hover — lifts to --shadow-lift"
            state="hover"
            variant="elevated"
          />
        </div>
        <p className={noteClass}>
          The root anchor is the single interaction target — content inside is plain text, so there
          is nothing nested to conflict. Flat variants lift to --shadow-subtle on hover; the
          already-elevated variant lifts to --shadow-lift.
        </p>
      </section>

      <section className={sectionClass} aria-labelledby="composition-heading">
        <h2 className="mb-2 text-xl" id="composition-heading">
          Composition (pattern B — inert root, real controls)
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Actions carry the interactivity — the root never gets the interactive flag.
        </p>
        <div className={demoGridClass}>
          <div className="grid gap-[var(--space-3)]">
            <span className={captionClass}>actions carry the interactivity — root stays inert</span>
            <Card>
              <CardHeader>
                <InitialsAvatar initials="AL" label="Ada Lovelace" />
                <div>
                  <CardTitle>Ada Lovelace</CardTitle>
                  <CardDescription>Analytical engine notes, 1843</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <p>Two independent targets below; the card surface itself is inert.</p>
              </CardContent>
              <CardActions>
                <Button size="sm">Invite</Button>
                <Button size="sm" variant="secondary">
                  View profile
                </Button>
              </CardActions>
            </Card>
          </div>
          <div className="grid gap-[var(--space-3)]">
            <span className={captionClass}>
              outlined + media + footer — parts remix freely across variants
            </span>
            <Card variant="outlined">
              <CardMedia>
                {/* biome-ignore lint/performance/noImgElement: data-URI 演示图,next/image 不优化内联资源 */}
                <img alt="Abstract cover: coral sun over a dark field" src={darkCoverImg} />
              </CardMedia>
              <CardTitle>Dark media on a light card</CardTitle>
              <CardContent>
                <p>Media is content, not a variant — any surface recipe accepts it.</p>
              </CardContent>
              <CardFooter>
                <CardDescription>
                  Footer divider uses --border-soft, the quiet hairline.
                </CardDescription>
              </CardFooter>
            </Card>
          </div>
        </div>
      </section>

      <section className="py-8" aria-labelledby="aliases-heading">
        <h2 className="mb-2 text-xl" id="aliases-heading">
          API aliases
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The spec ships a single padding (--space-8); the legacy size=&quot;sm&quot; maps to the
          nearest smaller spacing step (--space-6).
        </p>
        <div className="flex flex-wrap items-start gap-6">
          <Card>
            <CardTitle>size=default (--space-8)</CardTitle>
            <CardDescription>Spec padding</CardDescription>
          </Card>
          <Card size="sm">
            <CardTitle>size=sm (--space-6)</CardTitle>
            <CardDescription>Nearest smaller spacing step</CardDescription>
          </Card>
          <Card variant="outlined">
            <CardTitle>cardVariants exported</CardTitle>
            <CardDescription>For composing the surface recipe elsewhere</CardDescription>
          </Card>
        </div>
      </section>
    </main>
  )
}
