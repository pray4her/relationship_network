import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

/**
 * Tabs 预览页 —— 对应 showcase/tabs.html:
 * 2 variant(underline=line / contained=default)× 6 state 矩阵、3 size、
 * 内容配置、live 键盘导航样品与窄容器 overflow。
 * hover/pressed/focus-visible 经 data-[state=*] 镜像静态渲染(见 ui/tabs.tsx 注释);
 * selected 经真实 defaultValue 渲染(aria-selected / data-active)。
 */
const variants = [
  { label: "underline", variant: "line", text: "Overview" },
  { label: "contained", variant: "default", text: "All" },
] as const

const states = [
  { label: "default", props: {}, selected: false },
  { label: "hover", props: { "data-state": "hover" }, selected: false },
  { label: "pressed", props: { "data-state": "active" }, selected: false },
  { label: "focus-visible", props: { "data-state": "focus-visible" }, selected: false },
  { label: "disabled", props: { disabled: true }, selected: false },
  { label: "selected", props: {}, selected: true },
] as const

const sizes = [
  { label: "sm — 32px token", size: "sm" },
  { label: "md — 40px token", size: "default" },
  { label: "lg — 48px token", size: "lg" },
] as const

const userIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <circle cx="8" cy="5.5" r="2.5" stroke="currentColor" />
    <path
      d="M3 13.5c.8-2.2 2.7-3.5 5-3.5s4.2 1.3 5 3.5"
      stroke="currentColor"
      strokeLinecap="round"
    />
  </svg>
)

const cardIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <rect x="2.5" y="3.5" width="11" height="9" rx="1.5" stroke="currentColor" />
    <path d="M2.5 6.5h11" stroke="currentColor" />
  </svg>
)

const docIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <path
      d="M4 2.5h8a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1Z"
      stroke="currentColor"
    />
    <path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const thClass = "border-border-soft border-r border-b bg-surface-soft p-3 text-left align-middle"
const tdClass = "border-border-soft border-r border-b p-3 align-middle"
const rowHeadClass = `${tdClass} bg-card`

export default function TabsPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Tabs</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Two variants (underline, contained), three sizes, six states — every value a token
          reference. Selection is styled from aria-selected, never a parallel class.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          State matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Underline: quiet rail, muted labels that darken through the hover/active pair, and a
          primary indicator for the selected tab. Contained: the design spec's "Category tabs"
          recipe — accent on hover, selected-bg when selected.
        </p>

        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-popover shadow-subtle">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr>
                <th className={thClass} scope="col">
                  Variant
                </th>
                {states.map((state) => (
                  <th className={thClass} key={state.label} scope="col">
                    {state.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {variants.map((row) => (
                <tr key={row.label}>
                  <th className={rowHeadClass} scope="row">
                    {row.label}
                  </th>
                  {states.map((state) => (
                    <td className={tdClass} key={state.label}>
                      <Tabs defaultValue={state.selected ? "tab" : null}>
                        <TabsList variant={row.variant} aria-label={`${row.label} ${state.label}`}>
                          <TabsTrigger value="tab" {...state.props}>
                            {row.text}
                          </TabsTrigger>
                        </TabsList>
                      </Tabs>
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
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Heights ride the shared control ladder; text steps caption → nav-link → title-sm; inline
          padding steps space-3 → tab-padding-inline → space-6.
        </p>

        {sizes.map((row) => (
          <div className="mb-4 flex flex-wrap items-center gap-4" key={row.label}>
            <span className="w-36 flex-none text-caption-foreground text-sm">{row.label}</span>
            <Tabs defaultValue="members">
              <TabsList variant="line" size={row.size} aria-label={`${row.label} underline`}>
                <TabsTrigger value="members">Members</TabsTrigger>
                <TabsTrigger value="invites">Invites</TabsTrigger>
                <TabsTrigger value="roles">Roles</TabsTrigger>
              </TabsList>
            </Tabs>
            <Tabs defaultValue="all">
              <TabsList variant="default" size={row.size} aria-label={`${row.label} contained`}>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="writing">Writing</TabsTrigger>
                <TabsTrigger value="coding">Coding</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        ))}
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="content-heading">
        <h2 className="mb-2 text-xl" id="content-heading">
          Content configurations
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Icons size to --icon-size-sm (--icon-size-md on lg tabs) and inherit currentColor; badges
          are composed unmodified — the --space-2 gap does the spacing.
        </p>

        <Tabs defaultValue="text">
          <TabsList variant="line" aria-label="Content configurations">
            <TabsTrigger value="text">Text only</TabsTrigger>
            <TabsTrigger value="icon">
              {userIcon}
              Icon + text
            </TabsTrigger>
            <TabsTrigger value="badge">
              With badge
              <Badge aria-label="12 items">12</Badge>
            </TabsTrigger>
            <TabsTrigger value="everything">
              {cardIcon}
              Everything
              <Badge aria-label="3 new" variant="secondary">
                3
              </Badge>
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="mt-6">
          <Tabs defaultValue="text">
            <TabsList variant="default" aria-label="Contained content configurations">
              <TabsTrigger value="text">Text only</TabsTrigger>
              <TabsTrigger value="icon">
                {userIcon}
                Icon + text
              </TabsTrigger>
              <TabsTrigger value="badge">
                With badge
                <Badge aria-label="8 items" variant="secondary">
                  8
                </Badge>
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="live-heading">
        <h2 className="mb-2 text-xl" id="live-heading">
          Live — keyboard navigation
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Tab into a tablist, then ArrowLeft/ArrowRight to move, Home/End to jump — the disabled tab
          is skipped. Panels are focusable so keyboard users can continue into the content.
        </p>

        <Tabs defaultValue="general">
          <TabsList variant="line" aria-label="Tenant settings sections">
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="members">
              Members
              <Badge aria-label="24 members">24</Badge>
            </TabsTrigger>
            <TabsTrigger value="billing">Billing</TabsTrigger>
            <TabsTrigger value="danger" disabled>
              Danger zone
            </TabsTrigger>
          </TabsList>
          <TabsContent value="general" className="max-w-prose">
            <p className="text-foreground-body">
              General settings: tenant name, locale, and the public profile shown to candidates.
            </p>
          </TabsContent>
          <TabsContent value="members" className="max-w-prose">
            <p className="text-foreground-body">
              Invite members, assign roles, and review pending invitations.
            </p>
          </TabsContent>
          <TabsContent value="billing" className="max-w-prose">
            <p className="text-foreground-body">
              Current plan, invoices, and usage for this billing period.
            </p>
          </TabsContent>
          <TabsContent value="danger" className="max-w-prose">
            <p className="text-foreground-body">
              Destructive tenant operations. Disabled while the tenant is read-only.
            </p>
          </TabsContent>
        </Tabs>

        <div className="mt-8">
          <Tabs defaultValue="all">
            <TabsList variant="default" aria-label="Content categories">
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="writing">
                {docIcon}
                Writing
              </TabsTrigger>
              <TabsTrigger value="coding">Coding</TabsTrigger>
              <TabsTrigger value="analysis" disabled>
                Analysis
              </TabsTrigger>
            </TabsList>
            <TabsContent value="all" className="max-w-prose">
              <p className="text-foreground-body">Everything, across all categories.</p>
            </TabsContent>
            <TabsContent value="writing" className="max-w-prose">
              <p className="text-foreground-body">Long-form writing and documentation samples.</p>
            </TabsContent>
            <TabsContent value="coding" className="max-w-prose">
              <p className="text-foreground-body">Code walkthroughs and repository links.</p>
            </TabsContent>
            <TabsContent value="analysis" className="max-w-prose">
              <p className="text-foreground-body">Analysis artifacts.</p>
            </TabsContent>
          </Tabs>
        </div>
      </section>

      <section className="py-8" aria-labelledby="overflow-heading">
        <h2 className="mb-2 text-xl" id="overflow-heading">
          Overflow — narrow container
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Tabs never wrap or squash: the list scrolls horizontally and keeps --ring-width of
          breathing room so the focus ring is never clipped by the scroller.
        </p>

        <div className="max-w-sm">
          <Tabs defaultValue="offers">
            <TabsList variant="line" aria-label="Workflow stages (scrollable)">
              <TabsTrigger value="sourcing">Sourcing</TabsTrigger>
              <TabsTrigger value="screening">Screening</TabsTrigger>
              <TabsTrigger value="interviews">Interviews</TabsTrigger>
              <TabsTrigger value="assessments">Assessments</TabsTrigger>
              <TabsTrigger value="references">References</TabsTrigger>
              <TabsTrigger value="offers">Offers</TabsTrigger>
              <TabsTrigger value="onboarding">Onboarding</TabsTrigger>
            </TabsList>
            <TabsContent value="offers">
              <p className="text-foreground-body">
                The selected tab scrolls into view when reached by keyboard.
              </p>
            </TabsContent>
          </Tabs>
        </div>
      </section>
    </main>
  )
}
