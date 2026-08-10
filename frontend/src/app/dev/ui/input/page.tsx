import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

/**
 * Input 预览页 —— 对应 showcase/input.html:
 * 8 态状态矩阵 + 内容槽位 + 规格尺寸 + token 映射。
 * 状态经控件上的 data-state / aria-invalid / disabled / readOnly 渲染,
 * wrap 经 :has 读取(见 ui/input.tsx 注释)。
 */
type StateDemo = {
  readonly name: string
  readonly label: string
  readonly help: string
  readonly inputProps: {
    readonly id: string
    readonly type?: "email" | "text"
    readonly placeholder?: string
    readonly defaultValue?: string
    readonly required?: boolean
    readonly disabled?: boolean
    readonly readOnly?: boolean
    readonly "aria-describedby"?: string
    readonly "aria-invalid"?: boolean
    readonly "data-state"?: "hover" | "focus-visible" | "success"
  }
  readonly feedback?: { readonly tone: "error" | "success"; readonly text: string }
}

const states: readonly StateDemo[] = [
  {
    name: "Default",
    label: "Work email",
    help: "Used for invitations and security notices.",
    inputProps: {
      id: "preview-input-default",
      type: "email",
      placeholder: "you@company.com",
      required: true,
      "aria-describedby": "preview-input-default-help",
    },
  },
  {
    name: "Hover",
    label: "Job title",
    help: "Hover uses the shared strong border token.",
    inputProps: {
      id: "preview-input-hover",
      type: "text",
      placeholder: "Staff Engineer",
      required: true,
      "data-state": "hover",
      "aria-describedby": "preview-input-hover-help",
    },
  },
  {
    name: "Focus-visible",
    label: "Company name",
    help: "Focus uses the shared semantic ring and primary border tokens.",
    inputProps: {
      id: "preview-input-focus",
      type: "text",
      placeholder: "Northwind Labs",
      required: true,
      "data-state": "focus-visible",
      "aria-describedby": "preview-input-focus-help",
    },
  },
  {
    name: "Filled",
    label: "Full name",
    help: "Entered values use the primary foreground text token.",
    inputProps: {
      id: "preview-input-filled",
      type: "text",
      defaultValue: "Ada Lovelace",
      required: true,
      "aria-describedby": "preview-input-filled-help",
    },
  },
  {
    name: "Error",
    label: "Work email",
    help: "Use the address associated with your organization.",
    inputProps: {
      id: "preview-input-error",
      type: "email",
      defaultValue: "ada@lovelace",
      required: true,
      "aria-invalid": true,
      "aria-describedby": "preview-input-error-help",
    },
    feedback: { tone: "error", text: "Enter a complete email address, including a domain." },
  },
  {
    name: "Success",
    label: "Work email",
    help: "Success is expressed via data-state on the control (no native attribute exists).",
    inputProps: {
      id: "preview-input-success",
      type: "email",
      defaultValue: "ada@lovelace.example",
      required: true,
      "data-state": "success",
      "aria-describedby": "preview-input-success-help",
    },
    feedback: { tone: "success", text: "✓ Email address verified." },
  },
  {
    name: "Disabled",
    label: "Tenant slug",
    help: "Locked after tenant creation.",
    inputProps: {
      id: "preview-input-disabled",
      type: "text",
      defaultValue: "northwind",
      required: true,
      disabled: true,
      "aria-describedby": "preview-input-disabled-help",
    },
  },
  {
    name: "Read-only",
    label: "Workspace URL",
    help: "Read-only content remains focusable, selectable, and copyable.",
    inputProps: {
      id: "preview-input-readonly",
      type: "text",
      defaultValue: "https://app.example.com/northwind",
      required: true,
      readOnly: true,
      "aria-describedby": "preview-input-readonly-help",
    },
  },
]

const searchIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <circle cx="7" cy="7" r="4.5" stroke="currentColor" />
    <path d="m10.5 10.5 3 3" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const mailIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 16 16">
    <rect height="9" rx="2" stroke="currentColor" width="12" x="2" y="4" />
    <path
      d="m2.5 5 5.5 4 5.5-4"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const cardClass = "rounded-[var(--radius-lg)] border border-border bg-card p-6"
const tokenMap: readonly { readonly label: string; readonly tokens: readonly string[] }[] = [
  { label: "Focus-visible", tokens: ["--primary", "--ring-width", "--ring-focus"] },
  { label: "Error", tokens: ["--destructive", "--ring-destructive"] },
  { label: "Disabled", tokens: ["--opacity-disabled"] },
  { label: "Read-only", tokens: ["--muted"] },
  { label: "Chrome", tokens: ["--input", "--border-width", "--radius-md"] },
]

export default function InputPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Input</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Eight explicit states using native inputs inside token-driven field chrome. Labels,
          placeholders, entered values, helper text, and validation messaging are composed with
          Field while Input retains ownership of border, focus, disabled, and read-only visuals.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          Complete state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Static hover and focus mirrors are read from the control via :has; the same selectors
          respond to native interaction.
        </p>

        <div className="grid max-w-xl gap-4">
          {states.map((state) => (
            <article className={cardClass} key={state.name}>
              <span className="mb-4 block text-primary text-xs uppercase">{state.name}</span>
              <Field>
                <FieldLabel htmlFor={state.inputProps.id}>
                  {state.label}{" "}
                  <span aria-hidden="true" className="text-destructive">
                    *
                  </span>
                </FieldLabel>
                <Input {...state.inputProps} />
                <FieldDescription id={`${state.inputProps.id}-help`}>{state.help}</FieldDescription>
                {state.feedback?.tone === "error" ? (
                  <FieldError>{state.feedback.text}</FieldError>
                ) : null}
                {state.feedback?.tone === "success" ? (
                  <p className="font-medium text-success text-xs" role="status">
                    {state.feedback.text}
                  </p>
                ) : null}
              </Field>
            </article>
          ))}
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="slots-heading">
        <h2 className="mb-2 text-xl" id="slots-heading">
          Content slots
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Icons and affixes stay inside the same field frame without changing control semantics.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className={`${cardClass} grid content-start gap-3`}>
            <h3 className="text-base font-medium">Plain text</h3>
            <Input aria-label="Company name" placeholder="Company name" type="text" />
          </article>
          <article className={`${cardClass} grid content-start gap-3`}>
            <h3 className="text-base font-medium">Leading icon</h3>
            <Input
              aria-label="Search members"
              leadingIcon={searchIcon}
              placeholder="Search members"
              type="text"
            />
          </article>
          <article className={`${cardClass} grid content-start gap-3`}>
            <h3 className="text-base font-medium">Trailing icon</h3>
            <Input
              aria-label="Email"
              placeholder="you@company.com"
              trailingIcon={mailIcon}
              type="email"
            />
          </article>
          <article className={`${cardClass} grid content-start gap-3`}>
            <h3 className="text-base font-medium">Prefix and suffix</h3>
            <Input
              aria-label="Hourly rate"
              placeholder="120"
              prefix="$"
              suffix="USD / hr"
              type="number"
            />
          </article>
        </div>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="sizes-heading">
        <h2 className="mb-2 text-xl" id="sizes-heading">
          Sizes
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Spec heights --control-height-sm / --control-height / --control-height-lg; sm also drops
          the control text to --text-body-sm.
        </p>
        <div className="grid max-w-xl gap-4">
          <Input aria-label="Small input" placeholder="sm (32px)" size="sm" type="text" />
          <Input aria-label="Default input" placeholder="default (40px)" type="text" />
          <Input aria-label="Large input" placeholder="lg (48px)" size="lg" type="text" />
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-2 text-xl" id="mapping-heading">
          Token map
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          {tokenMap.map((entry) => (
            <article className={cardClass} key={entry.label}>
              <p className="font-medium text-sm">{entry.label}</p>
              <p className="mt-2 grid gap-1 text-muted-foreground text-xs">
                {entry.tokens.map((token) => (
                  <code key={token}>{token}</code>
                ))}
              </p>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}
