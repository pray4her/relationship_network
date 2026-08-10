import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableActions,
  TableBody,
  TableCell,
  TableCheckbox,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
  TableSortButton,
  TableSortIcon,
} from "@/components/ui/table"

/**
 * Table 预览页 —— 对应 showcase/table.html,逐节复刻:
 * Basic / Avatar+text / Sortable / Selectable / Row actions / Row states / Footer / Narrow。
 * 行态经 data-[state=*] 镜像静态渲染(见 ui/table.tsx 注释)。
 *
 * 组合缺口(其他原语并行迁移中,落地后此处替换为组件组合):
 * - Avatar+text 节:ui/avatar.tsx 尚未存在,本节先渲染文字单元格结构。
 * - 选择列:TableCheckbox 以 accent-color(--primary)对齐 checkbox.css 规格,ui/checkbox.tsx 落地后可换组合。
 * - Status badge 变体映射(showcase badge--success/warning/info/solid-primary 暂无对应):
 *   Active→default,In review→secondary,New match→outline,Draft→ghost,Suspended→destructive。
 */

const editIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path
      d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3Z"
      stroke="currentColor"
      strokeLinejoin="round"
    />
    <path d="m13.5 6.5 3 3" stroke="currentColor" />
  </svg>
)

const archiveIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path
      d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5V8M4 8h16M4 8v10.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V8"
      stroke="currentColor"
      strokeLinejoin="round"
    />
    <path d="M10 12h4" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const basicRows = [
  { name: "Ada Lovelace", role: "Senior Backend Engineer", match: "94%", status: "Active" },
  { name: "Grace Hopper", role: "Compiler Engineer", match: "88%", status: "In review" },
  { name: "Alan Turing", role: "Research Scientist", match: "81%", status: "New match" },
  { name: "Katherine Johnson", role: "Data Engineer", match: "76%", status: "Draft" },
] as const

const statusVariant = {
  Active: "default",
  "In review": "secondary",
  "New match": "outline",
  Draft: "ghost",
  Suspended: "destructive",
} as const

const sortStates = [
  { label: "Unsorted", ariaSort: "none", props: {} },
  { label: "Ascending", ariaSort: "ascending", props: {} },
  { label: "Descending", ariaSort: "descending", props: {} },
  { label: "Hover", ariaSort: "none", props: { "data-state": "hover" } },
  { label: "Focus-visible", ariaSort: "none", props: { "data-state": "focus-visible" } },
] as const

const rowStates = [
  { label: "default", candidate: "Ada Lovelace", match: "94%", props: {} },
  { label: "hover", candidate: "Grace Hopper", match: "88%", props: { "data-state": "hover" } },
  {
    label: "selected",
    candidate: "Alan Turing",
    match: "81%",
    props: { "data-state": "selected" },
  },
  {
    label: "focus-within",
    candidate: "Katherine Johnson",
    match: "76%",
    props: { "data-state": "focus-visible" },
  },
  {
    label: "selected + focus-within",
    candidate: "Margaret Hamilton",
    match: "90%",
    props: { "data-state": "selected focus-visible" },
  },
] as const

const noteClass = "mt-4 max-w-xl text-muted-foreground text-xs"
const captionClass = "mb-3 text-caption-foreground text-sm"

export default function TablePreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Table</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          A data table with optional header, footer, sortable columns, row selection, and row
          actions — built entirely from tokens. Row states are mirrored via data-state attributes
          for static rendering.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="basic-heading">
        <h2 className="mb-6 text-xl" id="basic-heading">
          Basic — text, number, status cells
        </h2>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Candidate</TableHead>
              <TableHead scope="col">Role</TableHead>
              <TableHead className="text-end" scope="col">
                Match
              </TableHead>
              <TableHead scope="col">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {basicRows.map((row) => (
              <TableRow key={row.name}>
                <TableCell strong>{row.name}</TableCell>
                <TableCell>{row.role}</TableCell>
                <TableCell numeric>{row.match}</TableCell>
                <TableCell>
                  <Badge variant={statusVariant[row.status as keyof typeof statusVariant]}>
                    {row.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className={noteClass}>
          Header: surface-soft band with caption-up text in muted-foreground; body rows over quiet
          border-soft dividers, none drawn under the last row. Hover any row: surface-soft fill.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="avatar-heading">
        <h2 className="mb-6 text-xl" id="avatar-heading">
          Avatar + text cell
        </h2>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Member</TableHead>
              <TableHead scope="col">Team</TableHead>
              <TableHead className="text-end" scope="col">
                Openings
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell strong>Ada Lovelace</TableCell>
              <TableCell>Platform</TableCell>
              <TableCell numeric>12</TableCell>
            </TableRow>
            <TableRow>
              <TableCell strong>Unassigned reviewer</TableCell>
              <TableCell>Review</TableCell>
              <TableCell numeric>3</TableCell>
            </TableRow>
            <TableRow>
              <TableCell strong>Grace Hopper</TableCell>
              <TableCell>Infrastructure</TableCell>
              <TableCell numeric>7</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p className={noteClass}>
          The identity cell composes the Avatar component (xs) beside a strong name cell — pending
          ui/avatar.tsx; structure only for now. No table-specific values.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="sort-heading">
        <h2 className="mb-2 text-xl" id="sort-heading">
          Sortable header state matrix
        </h2>
        <p className={captionClass}>
          The sorted column reads ink, the arrow flips, and aria-sort announces the direction; hover
          / focus-visible mirrored via data-state.
        </p>
        <div className="mb-6">
          <Table className="min-w-[560px]">
            <TableHeader>
              <TableRow>
                {sortStates.map((state) => (
                  <TableHead aria-sort={state.ariaSort} key={state.label} scope="col">
                    <TableSortButton {...state.props}>
                      {state.label}
                      <TableSortIcon />
                    </TableSortButton>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
          </Table>
        </div>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead aria-sort="ascending" scope="col">
                <TableSortButton>
                  Candidate
                  <TableSortIcon />
                </TableSortButton>
              </TableHead>
              <TableHead aria-sort="none" scope="col">
                <TableSortButton>
                  Match score
                  <TableSortIcon />
                </TableSortButton>
              </TableHead>
              <TableHead aria-sort="none" scope="col">
                <TableSortButton>
                  Applications
                  <TableSortIcon />
                </TableSortButton>
              </TableHead>
              <TableHead scope="col">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {basicRows.map((row) => (
              <TableRow key={row.name}>
                <TableCell strong>{row.name}</TableCell>
                <TableCell numeric>{Number.parseInt(row.match, 10)}</TableCell>
                <TableCell numeric>{row.name.length % 13}</TableCell>
                <TableCell>
                  <Badge variant={statusVariant[row.status as keyof typeof statusVariant]}>
                    {row.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className={noteClass}>
          The sort control is a borderless button inheriting the header caption-up typography;
          direction lives in aria-sort — CSS swaps the arrow from the attribute.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="select-heading">
        <h2 className="mb-2 text-xl" id="select-heading">
          Selectable row state matrix
        </h2>
        <p className={captionClass}>
          Selected rows take the selected-bg fill with a coral leading edge; the header checkbox
          selects all and turns indeterminate for partial selections.
        </p>
        <div className="mb-6">
          <Table className="min-w-[560px]">
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Selection state</TableHead>
                <TableHead scope="col">Control</TableHead>
                <TableHead scope="col">Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell strong>unchecked</TableCell>
                <TableCell>
                  <TableCheckbox aria-label="Unchecked row example" />
                </TableCell>
                <TableCell>Available</TableCell>
              </TableRow>
              <TableRow data-state="selected">
                <TableCell strong>checked</TableCell>
                <TableCell>
                  <TableCheckbox aria-label="Checked row example" defaultChecked />
                </TableCell>
                <TableCell>Selected</TableCell>
              </TableRow>
              <TableRow>
                <TableCell strong>indeterminate select-all</TableCell>
                <TableCell>
                  <TableCheckbox aria-label="Partially selected example" indeterminate />
                </TableCell>
                <TableCell>Some rows selected</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">
                <TableCheckbox aria-label="Select all candidates" />
              </TableHead>
              <TableHead scope="col">Candidate</TableHead>
              <TableHead scope="col">Role</TableHead>
              <TableHead className="text-end" scope="col">
                Match
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {basicRows.map((row) => (
              <TableRow key={row.name}>
                <TableCell>
                  <TableCheckbox aria-label={`Select ${row.name}`} />
                </TableCell>
                <TableCell strong>{row.name}</TableCell>
                <TableCell>{row.role}</TableCell>
                <TableCell numeric>{row.match}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className={noteClass}>
          Selection paint is the selected-bg fill plus a selected-border leading edge drawn as an
          inset shadow. Checkboxes use the native accent-color mapped to --primary per the checkbox
          spec (size --checkbox-size-md).
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="actions-heading">
        <h2 className="mb-6 text-xl" id="actions-heading">
          Row actions
        </h2>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Tenant</TableHead>
              <TableHead scope="col">Plan</TableHead>
              <TableHead className="text-end" scope="col">
                Seats
              </TableHead>
              <TableHead scope="col">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell strong>Northwind Labs</TableCell>
              <TableCell>
                <Badge>Pro</Badge>
              </TableCell>
              <TableCell numeric>24</TableCell>
              <TableCell>
                <TableActions>
                  <Button aria-label="Edit Northwind Labs" size="icon-sm" variant="ghost">
                    {editIcon}
                  </Button>
                  <Button aria-label="Archive Northwind Labs" size="icon-sm" variant="ghost">
                    {archiveIcon}
                  </Button>
                </TableActions>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell strong>Contoso Recruiting</TableCell>
              <TableCell>
                <Badge variant="outline">Free</Badge>
              </TableCell>
              <TableCell numeric>5</TableCell>
              <TableCell>
                <TableActions>
                  <Button aria-label="Edit Contoso Recruiting" size="icon-sm" variant="ghost">
                    {editIcon}
                  </Button>
                  <Button aria-label="Archive Contoso Recruiting" size="icon-sm" variant="ghost">
                    {archiveIcon}
                  </Button>
                </TableActions>
              </TableCell>
            </TableRow>
            <TableRow aria-disabled="true" data-state="disabled">
              <TableCell strong>Fabrikam GmbH</TableCell>
              <TableCell>
                <Badge variant="destructive">Suspended</Badge>
              </TableCell>
              <TableCell numeric>11</TableCell>
              <TableCell>
                <TableActions>
                  <Button aria-label="Edit Fabrikam GmbH" disabled size="icon-sm" variant="ghost">
                    {editIcon}
                  </Button>
                  <Button
                    aria-label="Archive Fabrikam GmbH"
                    disabled
                    size="icon-sm"
                    variant="ghost"
                  >
                    {archiveIcon}
                  </Button>
                </TableActions>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p className={noteClass}>
          Actions are ghost icon buttons in a space-1 flex row. The suspended row shows the
          disabled-row treatment: reduced opacity over the whole row, no hover, natively disabled
          action buttons.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          Row states
        </h2>
        <p className={captionClass}>
          States below are forced with data-state mirrors; in a live table they come from :hover,
          selection, and :focus-within.
        </p>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">State</TableHead>
              <TableHead scope="col">Candidate</TableHead>
              <TableHead className="text-end" scope="col">
                Match
              </TableHead>
              <TableHead scope="col">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rowStates.map((state) => (
              <TableRow key={state.label} {...state.props}>
                <TableCell strong>{state.label}</TableCell>
                <TableCell>{state.candidate}</TableCell>
                <TableCell numeric>{state.match}</TableCell>
                <TableCell>
                  <TableActions>
                    <Button aria-label={`Edit ${state.label} row`} size="icon-sm" variant="ghost">
                      {editIcon}
                    </Button>
                  </TableActions>
                </TableCell>
              </TableRow>
            ))}
            <TableRow aria-disabled="true" data-state="disabled">
              <TableCell strong>disabled</TableCell>
              <TableCell>Withdrawn candidate</TableCell>
              <TableCell numeric>—</TableCell>
              <TableCell>
                <TableActions>
                  <Button aria-label="Edit disabled row" disabled size="icon-sm" variant="ghost">
                    {editIcon}
                  </Button>
                </TableActions>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p className={noteClass}>
          hover → surface-soft; selected → selected-bg + coral edge; focus-within → inset ring
          (composes with the selected edge — two inset shadows, zero conflict); disabled → reduced
          opacity and no hover.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="footer-heading">
        <h2 className="mb-6 text-xl" id="footer-heading">
          Footer
        </h2>
        <Table className="min-w-[560px]">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Job</TableHead>
              <TableHead className="text-end" scope="col">
                Candidates
              </TableHead>
              <TableHead className="text-end" scope="col">
                Quota used
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell strong>Staff Platform Engineer</TableCell>
              <TableCell numeric>32</TableCell>
              <TableCell numeric>14</TableCell>
            </TableRow>
            <TableRow>
              <TableCell strong>Senior Talent Partner</TableCell>
              <TableCell numeric>18</TableCell>
              <TableCell numeric>9</TableCell>
            </TableRow>
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell>Total</TableCell>
              <TableCell numeric>50</TableCell>
              <TableCell numeric>23</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
        <p className={noteClass}>
          The footer mirrors the header band: surface-soft fill, a border hairline on top, and the
          caption recipe in caption-foreground.
        </p>
      </section>

      <section className="py-8" aria-labelledby="responsive-heading">
        <h2 className="mb-2 text-xl" id="responsive-heading">
          Narrow viewports
        </h2>
        <p className={captionClass}>
          The container below is capped at 150px — the wrap scrolls horizontally instead of the
          table re-inventing itself.
        </p>
        <div className="max-w-[150px]">
          <Table className="min-w-[560px]">
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Candidate</TableHead>
                <TableHead scope="col">Role</TableHead>
                <TableHead className="text-end" scope="col">
                  Match
                </TableHead>
                <TableHead scope="col">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {basicRows.slice(0, 2).map((row) => (
                <TableRow key={row.name}>
                  <TableCell strong>{row.name}</TableCell>
                  <TableCell>{row.role}</TableCell>
                  <TableCell numeric>{row.match}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant[row.status as keyof typeof statusVariant]}>
                      {row.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className={noteClass}>
          Responsive strategy: overflow-x auto on the wrap, overflow-y visible kept for sticky
          headers. The min-width comes from the page context, never from the component.
        </p>
      </section>
    </main>
  )
}
