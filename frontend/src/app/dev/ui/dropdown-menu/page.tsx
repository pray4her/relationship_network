import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

/**
 * DropdownMenu 预览页 —— 对应 showcase/dropdown-menu.html:
 * 全状态矩阵(6 列)+ 交互演示 + 键盘导航表 + 开闭动效帧 + 滚动帽/窄列。
 * 矩阵单元格与动效/滚动演示均渲染 defaultOpen 的真实菜单(modal={false} 以便同屏
 * 多个面板共存);单元格预留 min-height 供 Portal 面板落位。
 * 状态经 data-[state=hover|focus-visible|opening|closing] 镜像静态渲染
 * (见 ui/dropdown-menu.tsx 注释)。
 */
const hover = { "data-state": "hover" } as const
const focusVisible = { "data-state": "focus-visible" } as const

const pencilIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <path
      d="M10.9 2.6a1.5 1.5 0 0 1 2.1 2.1L5.4 12.3 2 13.5l1.2-3.4Z"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const copyIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <rect height="8.5" rx="1.5" stroke="currentColor" width="8.5" x="5" y="5" />
    <path d="M3 11V3.5A.5.5 0 0 1 3.5 3H11" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const trashIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <path
      d="M2.5 4h11M6.5 4V2.5h3V4M4 4l.8 9.5h6.4L12 4"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const shareIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <path
      d="M13.5 7 8 1.5 2.5 7M8 2v9.5"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const cellClass = "rounded-[var(--radius-md)] border border-border-soft bg-background"
const cellTitleClass =
  "px-4 pt-4 pb-3 text-muted-foreground text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] font-medium"
const cellBodyClass = "min-h-[calc(var(--space-16)*8)] px-4"

const thClass = "border-border-soft border-b p-2 text-left text-muted-foreground font-medium"
const tdClass = "border-border-soft border-b p-2 align-top"

const keyboardRows: ReadonlyArray<{ readonly keys: readonly string[]; readonly behavior: string }> =
  [
    {
      keys: ["Enter", "Space"],
      behavior:
        "On the trigger: opens the menu and focuses the first item. On an item: activates it.",
    },
    {
      keys: ["↓", "↑"],
      behavior: "Move focus to the next / previous enabled item, wrapping at the ends.",
    },
    { keys: ["Home", "End"], behavior: "Focus the first / last enabled item of the open panel." },
    { keys: ["→"], behavior: "On a submenu trigger: opens the branch and focuses its first item." },
    {
      keys: ["←", "Esc"],
      behavior:
        "Inside a submenu: closes it and returns focus to its trigger. Esc on the root closes the menu and refocuses the trigger.",
    },
    {
      keys: ["Tab"],
      behavior:
        "Closes the menu; the tab order holds exactly one item per panel (roving tabindex).",
    },
    {
      keys: ["a–z"],
      behavior:
        "Type-ahead: focus jumps to the next item whose label starts with the typed letters.",
    },
  ]

const motionFrames = [
  { label: "Open — opacity 1, settled at --space-2", props: {} },
  { label: "Opening — --opacity-disabled, mid-travel", props: { "data-state": "opening" } },
  { label: "Closing — fading over --duration-fast", props: { "data-state": "closing" } },
] as const

const members = [
  "Ada Lindqvist",
  "Beatriz Costa",
  "Chen Wei",
  "Dmitri Novak",
  "Elif Demir",
  "Farah Haddad",
  "Grace Okafor",
  "Hiro Tanaka",
] as const

export default function DropdownMenuPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">DropdownMenu</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          The complete matrix in one preview: every item type — standard, icon + label, keyboard
          shortcut, checkbox, radio, group label, separator, submenu trigger, destructive — rendered
          across every interaction state.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Full matrix — every item type, every state
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Each cell is a real defaultOpen menu; highlighted / focus states mirrored via data-state
          attributes.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] items-start gap-8">
          <article className={cellClass}>
            <h3 className={cellTitleClass}>Item types · default</h3>
            <div className={cellBodyClass}>
              <DropdownMenu defaultOpen modal={false}>
                <DropdownMenuTrigger render={<Button variant="secondary">Item types</Button>} />
                <DropdownMenuContent>
                  <DropdownMenuItem>Standard item</DropdownMenuItem>
                  <DropdownMenuItem>{pencilIcon}Icon + label</DropdownMenuItem>
                  <DropdownMenuItem>
                    With shortcut<DropdownMenuShortcut>⌘D</DropdownMenuShortcut>
                  </DropdownMenuItem>
                  <DropdownMenuCheckboxItem>Checkbox item</DropdownMenuCheckboxItem>
                  <DropdownMenuRadioGroup defaultValue="radio">
                    <DropdownMenuRadioItem value="radio">Radio item</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                  <DropdownMenuSeparator />
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>Group label</DropdownMenuLabel>
                  </DropdownMenuGroup>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>Submenu trigger</DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem>Branch item</DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuItem variant="destructive">Destructive item</DropdownMenuItem>
                  <DropdownMenuItem disabled>Disabled item</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </article>

          <article className={cellClass}>
            <h3 className={cellTitleClass}>Highlighted · hover / keyboard focus fill = --accent</h3>
            <div className={cellBodyClass}>
              <DropdownMenu defaultOpen modal={false}>
                <DropdownMenuTrigger render={<Button variant="secondary">Highlighted</Button>} />
                <DropdownMenuContent>
                  <DropdownMenuItem {...hover}>Standard · highlighted</DropdownMenuItem>
                  <DropdownMenuItem {...hover}>
                    {pencilIcon}Icon + label · highlighted
                  </DropdownMenuItem>
                  <DropdownMenuCheckboxItem defaultChecked {...hover}>
                    Checked · highlighted
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuItem variant="destructive" {...hover}>
                    Destructive · highlighted
                  </DropdownMenuItem>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger {...hover}>
                      Submenu trigger · hover
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem>Branch item</DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </article>

          <article className={cellClass}>
            <h3 className={cellTitleClass}>
              Focus · 0 0 0 --ring-width --ring-focus (rides :focus — roving focus is programmatic)
            </h3>
            <div className={cellBodyClass}>
              <DropdownMenu defaultOpen modal={false}>
                <DropdownMenuTrigger render={<Button variant="secondary">Focus</Button>} />
                <DropdownMenuContent>
                  <DropdownMenuItem {...focusVisible}>Standard · focus</DropdownMenuItem>
                  <DropdownMenuCheckboxItem defaultChecked {...focusVisible}>
                    Checked · focus (ring over fill)
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuItem variant="destructive" {...focusVisible}>
                    Destructive · focus
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </article>

          <article className={cellClass}>
            <h3 className={cellTitleClass}>
              Selected · reserved indicator slot, currentColor glyph
            </h3>
            <div className={cellBodyClass}>
              <DropdownMenu defaultOpen modal={false}>
                <DropdownMenuTrigger render={<Button variant="secondary">Selected</Button>} />
                <DropdownMenuContent>
                  <DropdownMenuCheckboxItem>Checkbox · unchecked</DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem defaultChecked>
                    Checkbox · checked
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuRadioGroup defaultValue="name">
                    <DropdownMenuRadioItem value="date">Radio · unselected</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="name">Radio · selected</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                  <DropdownMenuCheckboxItem defaultChecked disabled>
                    Checked · disabled
                  </DropdownMenuCheckboxItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </article>

          <article className={cellClass}>
            <h3 className={cellTitleClass}>
              Destructive · --destructive / -hover / -active · disabled · --opacity-disabled
            </h3>
            <div className={cellBodyClass}>
              <DropdownMenu defaultOpen modal={false}>
                <DropdownMenuTrigger render={<Button variant="secondary">Destructive</Button>} />
                <DropdownMenuContent>
                  <DropdownMenuItem variant="destructive">Destructive · default</DropdownMenuItem>
                  <DropdownMenuItem variant="destructive" {...hover}>
                    Destructive · hover (--destructive-hover)
                  </DropdownMenuItem>
                  <DropdownMenuItem variant="destructive">
                    {trashIcon}Destructive · icon + label
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled variant="destructive">
                    Destructive · disabled
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem disabled>{copyIcon}Disabled · icon + label</DropdownMenuItem>
                  <DropdownMenuCheckboxItem disabled>Disabled · checkbox</DropdownMenuCheckboxItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </article>

          <article className={cellClass}>
            <h3 className={cellTitleClass}>
              Submenu · trigger open (--accent holds), branch anchored --space-1 into the parent
              edge
            </h3>
            <div className={cellBodyClass}>
              <DropdownMenu defaultOpen modal={false}>
                <DropdownMenuTrigger render={<Button variant="secondary">Submenu</Button>} />
                <DropdownMenuContent>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>Branch · closed</DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem>Branch item</DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuSub defaultOpen>
                    <DropdownMenuSubTrigger>Branch · open trigger</DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem>Copy link</DropdownMenuItem>
                      <DropdownMenuItem>{shareIcon}Share upward</DropdownMenuItem>
                      <DropdownMenuItem variant="destructive">Revoke access</DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger disabled>Branch · disabled</DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem>Branch item</DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </article>
        </div>

        <p className="mt-4 max-w-2xl text-muted-foreground text-sm">
          Highlighted = --accent fill (hover AND keyboard focus — menu focus is programmatic, so the
          ring rides :focus). Selection never touches the surface: the reserved --icon-size-sm
          indicator slot shows a currentColor check (checkbox) or dot (radio). Destructive rows are
          --destructive text with the dedicated --destructive-hover / --destructive-active tokens.
          Disabled rows drop to --opacity-disabled and are skipped by the keyboard layer.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="live-heading">
        <h2 className="mb-2 text-xl" id="live-heading">
          Interactive — full keyboard navigation
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Open with Enter or Space, then drive it entirely from the keyboard. Checkbox items toggle
          and keep the menu open; radio items select within their group; activating an action closes
          the menu. Type a letter to jump to a matching item.
        </p>

        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="secondary">Project actions</Button>} />
          <DropdownMenuContent>
            <DropdownMenuGroup>
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuItem>View profile</DropdownMenuItem>
              <DropdownMenuItem>
                {pencilIcon}Edit name<DropdownMenuShortcut>⌘E</DropdownMenuShortcut>
              </DropdownMenuItem>
              <DropdownMenuItem>
                {copyIcon}Duplicate<DropdownMenuShortcut>⌘D</DropdownMenuShortcut>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuLabel>Preferences</DropdownMenuLabel>
              <DropdownMenuCheckboxItem defaultChecked>
                Email notifications
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem>Weekly digest</DropdownMenuCheckboxItem>
            </DropdownMenuGroup>
            <DropdownMenuGroup>
              <DropdownMenuLabel>Sort by</DropdownMenuLabel>
              <DropdownMenuRadioGroup defaultValue="name">
                <DropdownMenuRadioItem value="name">Name</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="date">Date modified</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="size">Size</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>{shareIcon}Share</DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                <DropdownMenuItem>
                  Copy link<DropdownMenuShortcut>⌘L</DropdownMenuShortcut>
                </DropdownMenuItem>
                <DropdownMenuItem>Email to team</DropdownMenuItem>
                <DropdownMenuItem disabled>Publish (no plan)</DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>Export</DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                <DropdownMenuItem>Export as CSV</DropdownMenuItem>
                <DropdownMenuItem>Export as JSON</DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuItem disabled>Archive (locked)</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive">{trashIcon}Delete project…</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="keys-heading">
        <h2 className="mb-6 text-xl" id="keys-heading">
          Keyboard navigation
        </h2>
        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-popover shadow-subtle">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className={thClass} scope="col">
                  Key
                </th>
                <th className={thClass} scope="col">
                  Behaviour
                </th>
              </tr>
            </thead>
            <tbody>
              {keyboardRows.map((row) => (
                <tr key={row.keys.join("-")}>
                  <td className={tdClass}>
                    {row.keys.map((key, index) => (
                      <span key={key}>
                        {index > 0 && " / "}
                        <kbd className="font-mono text-[length:var(--text-caption-up)] text-foreground-body">
                          {key}
                        </kbd>
                      </span>
                    ))}
                  </td>
                  <td className={tdClass}>{row.behavior}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="motion-heading">
        <h2 className="mb-2 text-xl" id="motion-heading">
          Open / close motion
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The tooltip/popover lifecycle reused verbatim: enter over --duration-normal, exit over
          --duration-fast, both on --ease-standard, parked --space-1 toward the trigger while
          closed. Submenus travel the same curves horizontally.
        </p>
        {motionFrames.map((frame) => (
          <div className="min-h-[calc(var(--space-16)*2)]" key={frame.label}>
            <DropdownMenu defaultOpen modal={false}>
              <DropdownMenuTrigger render={<Button variant="secondary">Motion frame</Button>} />
              <DropdownMenuContent className="max-w-[var(--sidebar-width)]" {...frame.props}>
                <DropdownMenuItem>{frame.label}</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ))}
      </section>

      <section className="py-8" aria-labelledby="scroll-heading">
        <h2 className="mb-2 text-xl" id="scroll-heading">
          Scroll cap &amp; narrow columns
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          The panel caps at --menu-max-height (six rows) and scrolls; arrow-key focus lands each row
          in view. The column is --sidebar-width wide — the panel&apos;s min-width — and the long
          name wraps because items carry a min-height floor, not a fixed height.
        </p>
        <div className="max-w-[var(--sidebar-width)]">
          <div className="min-h-[calc(var(--menu-max-height)+var(--control-height)+var(--space-16))]">
            <DropdownMenu defaultOpen modal={false}>
              <DropdownMenuTrigger render={<Button variant="secondary">Jump to member</Button>} />
              <DropdownMenuContent>
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Members</DropdownMenuLabel>
                  {members.map((member) => (
                    <DropdownMenuItem key={member}>{member}</DropdownMenuItem>
                  ))}
                  <DropdownMenuItem>
                    Ines Duarte with a deliberately long display name that wraps
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </section>
    </main>
  )
}
