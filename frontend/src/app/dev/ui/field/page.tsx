import {
  Field,
  FieldControl,
  FieldDescription,
  FieldError,
  FieldHeader,
  FieldLabel,
  FieldRequired,
  FieldSuccess,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

/**
 * FormField 预览页 —— 对应 showcase/form-field.html:
 * 7 个字段级状态矩阵 + token map。
 * 状态经 :has() 真实属性(disabled/readonly)与 data-[state=*] 镜像静态渲染
 * (见 ui/field.tsx 注释);focus-visible / success 卡片的状态环按 input.tsx 合同
 * 镜像在控件上(data-state="focus-visible" / "success"),Field 上的
 * data-state="focused" 只提亮 label。
 */
const cardClass =
  "grid gap-[var(--space-4)] rounded-[var(--radius-lg)] border border-border bg-card p-6"
const cardNameClass = "block text-primary text-xs uppercase"

export default function FieldPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">FormField</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Seven field-level states with complete label, required marker, control slot, helper, and
          validation anatomy. Input owns its chrome; FormField owns labeling, messaging, state
          coordination, and accessible relationships.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          Complete field state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Every control is labeled with <code>for</code> and <code>id</code>; helper and validation
          messages are referenced through <code>aria-describedby</code>.
        </p>

        <div className="grid max-w-xl gap-[var(--space-4)]">
          <article className={cardClass}>
            <span className={cardNameClass}>Default</span>
            <Field>
              <FieldHeader>
                <FieldLabel htmlFor="field-default">
                  Work email <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-default-help"
                  id="field-default"
                  placeholder="you@company.com"
                  required
                  type="email"
                />
              </FieldControl>
              <FieldDescription id="field-default-help">
                Invitations and security notices are sent here.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Focus-visible child</span>
            <Field data-state="focused">
              <FieldHeader>
                <FieldLabel htmlFor="field-focus">
                  Company name <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-focus-help"
                  data-state="focus-visible"
                  id="field-focus"
                  placeholder="Northwind Labs"
                  required
                  type="text"
                />
              </FieldControl>
              <FieldDescription id="field-focus-help">
                The label strengthens while the slotted control owns the focus ring.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Filled child</span>
            <Field>
              <FieldHeader>
                <FieldLabel htmlFor="field-filled">
                  Full name <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-filled-help"
                  defaultValue="Ada Lovelace"
                  id="field-filled"
                  required
                  type="text"
                />
              </FieldControl>
              <FieldDescription id="field-filled-help">
                Entered content remains distinct from placeholder text.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Disabled child</span>
            <Field>
              <FieldHeader>
                <FieldLabel htmlFor="field-disabled">
                  Tenant slug <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-disabled-help"
                  defaultValue="northwind"
                  disabled
                  id="field-disabled"
                  required
                  type="text"
                />
              </FieldControl>
              <FieldDescription id="field-disabled-help">
                Locked after tenant creation; field text uses the system disabled treatment.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Read-only child</span>
            <Field>
              <FieldHeader>
                <FieldLabel htmlFor="field-readonly">
                  Workspace URL <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-readonly-help"
                  defaultValue="https://app.example.com/northwind"
                  id="field-readonly"
                  readOnly
                  required
                  type="text"
                />
              </FieldControl>
              <FieldDescription id="field-readonly-help">
                Read-only content remains focusable and copyable.
              </FieldDescription>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Error</span>
            <Field data-invalid={true} data-state="error">
              <FieldHeader>
                <FieldLabel htmlFor="field-error">
                  Work email <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-error-help field-error-message"
                  aria-invalid={true}
                  defaultValue="ada@lovelace"
                  id="field-error"
                  required
                  type="email"
                />
              </FieldControl>
              <FieldDescription id="field-error-help">
                Use the address associated with your organization.
              </FieldDescription>
              <FieldError id="field-error-message">
                Enter a complete email address, including a domain.
              </FieldError>
            </Field>
          </article>

          <article className={cardClass}>
            <span className={cardNameClass}>Success</span>
            <Field data-state="success">
              <FieldHeader>
                <FieldLabel htmlFor="field-success">
                  Invite code <FieldRequired />
                </FieldLabel>
              </FieldHeader>
              <FieldControl>
                <Input
                  aria-describedby="field-success-help field-success-message"
                  data-state="success"
                  defaultValue="NWT-2026-8841"
                  id="field-success"
                  required
                  type="text"
                />
              </FieldControl>
              <FieldDescription id="field-success-help">
                Codes are validated against the active invitation.
              </FieldDescription>
              <FieldSuccess id="field-success-message">Invite code accepted.</FieldSuccess>
            </Field>
          </article>
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-6 text-xl" id="mapping-heading">
          Token map
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <p className="text-base font-medium">Label</p>
            <p className="mt-[var(--space-2)] grid gap-[var(--space-1)] text-muted-foreground text-xs">
              <code>--foreground-strong</code>
              <code>--text-caption</code>
              <code>--font-weight-medium</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <p className="text-base font-medium">Helper</p>
            <p className="mt-[var(--space-2)] grid gap-[var(--space-1)] text-muted-foreground text-xs">
              <code>--muted-foreground</code>
              <code>--font-weight-regular</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <p className="text-base font-medium">Error</p>
            <p className="mt-[var(--space-2)] grid gap-[var(--space-1)] text-muted-foreground text-xs">
              <code>--destructive</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <p className="text-base font-medium">Success</p>
            <p className="mt-[var(--space-2)] grid gap-[var(--space-1)] text-muted-foreground text-xs">
              <code>--success</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <p className="text-base font-medium">Disabled</p>
            <p className="mt-[var(--space-2)] grid gap-[var(--space-1)] text-muted-foreground text-xs">
              <code>--opacity-disabled</code>
            </p>
          </article>
          <article className="rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <p className="text-base font-medium">Spacing</p>
            <p className="mt-[var(--space-2)] grid gap-[var(--space-1)] text-muted-foreground text-xs">
              <code>--space-2</code>
              <code>--space-4</code>
            </p>
          </article>
        </div>
      </section>
    </main>
  )
}
