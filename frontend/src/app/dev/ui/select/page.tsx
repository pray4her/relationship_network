import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/**
 * Select 预览页 —— 对应 showcase/select.html:
 * 七个 trigger 状态卡(含一个完整展开的 listbox)+ 尺寸 + token map。
 * hover/focus-visible 经 data-state 镜像静态渲染(见 ui/select.tsx 注释);
 * open 卡经 defaultOpen 展开,option 高亮态用 data-state="hover" 镜像。
 */
const cardClass = "rounded-[var(--radius-lg)] border border-border bg-card p-6"
const cardNameClass = "mb-4 block text-primary text-xs uppercase"

// base-ui 仅在 popup 挂载后注册 ItemText;闭合态的 SelectValue 需经 Root 的
// items 建立 value → label 映射,否则回退渲染原始 value。
const regionItems = [
  { value: "eu-frankfurt", label: "EU (Frankfurt)" },
  { value: "us-east", label: "US East" },
]

export default function SelectPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Select</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Seven explicit trigger states plus one complete open listbox. Focus remains on the trigger
          while Arrow keys update the active descendant; Enter or Space commits and Escape
          dismisses.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          State matrix — closed and open
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Placeholder, selected value, chevron, helper, error, focus, and option interaction states
          use the same field and semantic tokens as Input.
        </p>

        <div className="grid max-w-3xl gap-4">
          <article className={cardClass}>
            <span className={cardNameClass}>Default · placeholder</span>
            <Field>
              <FieldLabel>Role</FieldLabel>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="owner">Owner</SelectItem>
                  <SelectItem value="member">Member</SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>
                Choose the member role used for tenant permissions.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Hover</span>
            <Field>
              <FieldLabel>Plan</FieldLabel>
              <Select>
                <SelectTrigger data-state="hover">
                  <SelectValue placeholder="Choose a plan" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="team">Team</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>Hover strengthens only the shared field border.</FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Focus-visible</span>
            <Field>
              <FieldLabel>Office</FieldLabel>
              <Select>
                <SelectTrigger data-state="focus-visible">
                  <SelectValue placeholder="Choose an office" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="berlin">Berlin</SelectItem>
                  <SelectItem value="remote">Remote</SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>
                The shared semantic focus ring matches Input exactly.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Filled</span>
            <Field>
              <FieldLabel>Region</FieldLabel>
              <Select defaultValue="eu-frankfurt" items={regionItems}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="eu-frankfurt">EU (Frankfurt)</SelectItem>
                  <SelectItem value="us-east">US East</SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>
                Selected values use primary foreground, never placeholder color.
              </FieldDescription>
            </Field>
          </article>

          {/* 规格的 .state-card--popup:panel 绝对定位悬在 trigger 下方,描述文本
          留在 trigger 之后(被面板遮住),卡片底部预留 --menu-max-height 空间 */}
          <article className={`${cardClass} pb-[calc(var(--menu-max-height)+var(--space-8))]`}>
            <span className={cardNameClass}>Open · complete option states</span>
            <Field>
              <FieldLabel>Sort members by</FieldLabel>
              <Select defaultOpen defaultValue="selected">
                <SelectTrigger>
                  <SelectValue>Recently active</SelectValue>
                </SelectTrigger>
                <SelectContent
                  alignItemWithTrigger={false}
                  collisionAvoidance={{ side: "none", align: "none", fallbackAxisSide: "none" }}
                >
                  <SelectItem value="default">Default option</SelectItem>
                  <SelectItem data-state="hover" value="highlighted">
                    Hover / highlighted option
                  </SelectItem>
                  <SelectItem value="selected">Selected + checked option</SelectItem>
                  <SelectItem disabled value="disabled">
                    Disabled option
                  </SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>
                Open holds focus, rotates the chevron, and exposes every option state together.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Error</span>
            <Field>
              <FieldLabel>
                Billing country{" "}
                <span aria-hidden="true" className="text-destructive">
                  *
                </span>
              </FieldLabel>
              <Select>
                <SelectTrigger aria-invalid={true}>
                  <SelectValue placeholder="Select a country" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="de">Germany</SelectItem>
                  <SelectItem value="uk">United Kingdom</SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>Used for invoices and tax handling.</FieldDescription>
              <FieldError>Select a billing country.</FieldError>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Disabled</span>
            <Field>
              <FieldLabel>Data region</FieldLabel>
              <Select defaultValue="eu-frankfurt" disabled items={regionItems}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="eu-frankfurt">EU (Frankfurt)</SelectItem>
                </SelectContent>
              </Select>
              <FieldDescription>
                The native disabled attribute blocks all interaction.
              </FieldDescription>
            </Field>
          </article>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="sizes-heading">
        <h2 className="mb-2 text-xl" id="sizes-heading">
          Sizes
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          sm / md / lg map to the shared control-height scale; sm switches to the small body text.
        </p>
        <div className="grid max-w-3xl gap-4">
          {(
            [
              { size: "sm", label: "sm — 32px" },
              { size: "default", label: "md — 40px" },
              { size: "lg", label: "lg — 48px" },
            ] as const
          ).map(({ size, label }) => (
            <article className={cardClass} key={size}>
              <span className={cardNameClass}>{label}</span>
              <Select defaultValue="eu-frankfurt" items={regionItems}>
                <SelectTrigger className="max-w-sm" size={size}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="eu-frankfurt">EU (Frankfurt)</SelectItem>
                  <SelectItem value="us-east">US East</SelectItem>
                </SelectContent>
              </Select>
            </article>
          ))}
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-6 text-xl" id="mapping-heading">
          Token map
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className={cardClass}>
            <p className="text-sm font-medium">Trigger</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--background / --foreground</code>
              <code>--input / --border-strong</code>
              <code>--control-height / --input-padding-inline</code>
            </p>
          </article>
          <article className={cardClass}>
            <p className="text-sm font-medium">Focus and validation</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--primary / --ring-focus / --ring-width</code>
              <code>--destructive / --ring-destructive</code>
              <code>--opacity-disabled</code>
            </p>
          </article>
          <article className={cardClass}>
            <p className="text-sm font-medium">Dropdown</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--popover / --border / --shadow-subtle</code>
              <code>--radius-md / --menu-max-height / --z-dropdown</code>
            </p>
          </article>
          <article className={cardClass}>
            <p className="text-sm font-medium">Options and motion</p>
            <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
              <code>--accent / --surface-cream-strong / --primary</code>
              <code>--duration-fast / --ease-standard</code>
              <code>--motion-rotation-full</code>
            </p>
          </article>
        </div>
      </section>
    </main>
  )
}
