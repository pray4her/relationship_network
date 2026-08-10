import type * as React from "react"

import { Input } from "@/components/ui/input"
import { Label, LabelRequired } from "@/components/ui/label"

/**
 * Label 预览页 —— 对应 showcase/form-field.html(只看 label 相关规格):
 * 7 个字段级状态卡片 + token map。
 * label 的派生状态(focus-visible/readonly/error/disabled)经 data-[state=*]
 * 镜像静态渲染(见 ui/label.tsx 注释);focus-visible / success 卡片的状态环
 * 按 input.tsx 合同镜像在控件上(data-state="focus-visible" / "success"),其余
 * 卡片控件槽只放入 Input 作上下文,控件自身的 chrome 由 input 规格负责。
 */
type StateDemo = {
  readonly name: string
  readonly label: string
  readonly labelProps: { "data-state"?: "focus-visible" | "disabled" | "readonly" | "error" }
  readonly inputProps: Omit<React.ComponentProps<"input">, "size"> & {
    /** input.tsx 静态镜像:focus-visible / success 态由控件上的 data-state 驱动。 */
    "data-state"?: "focus-visible" | "success"
  }
  readonly help: string
  readonly error?: string
  readonly success?: string
}

const states: readonly StateDemo[] = [
  {
    name: "Default",
    label: "Work email",
    labelProps: {},
    inputProps: { type: "email", placeholder: "you@company.com" },
    help: "Invitations and security notices are sent here.",
  },
  {
    name: "Focus-visible child",
    label: "Company name",
    labelProps: { "data-state": "focus-visible" },
    inputProps: { type: "text", placeholder: "Northwind Labs", "data-state": "focus-visible" },
    help: "The label strengthens while the slotted control owns the focus ring.",
  },
  {
    name: "Filled child",
    label: "Full name",
    labelProps: {},
    inputProps: { type: "text", defaultValue: "Ada Lovelace" },
    help: "Entered content remains distinct from placeholder text.",
  },
  {
    name: "Disabled child",
    label: "Tenant slug",
    labelProps: { "data-state": "disabled" },
    inputProps: { type: "text", defaultValue: "northwind", disabled: true },
    help: "Locked after tenant creation; field text uses the system disabled treatment.",
  },
  {
    name: "Read-only child",
    label: "Workspace URL",
    labelProps: { "data-state": "readonly" },
    inputProps: { type: "text", defaultValue: "https://app.example.com/northwind", readOnly: true },
    help: "Read-only content remains focusable and copyable.",
  },
  {
    name: "Error",
    label: "Work email",
    labelProps: { "data-state": "error" },
    inputProps: { type: "email", defaultValue: "ada@lovelace", "aria-invalid": true },
    help: "Use the address associated with your organization.",
    error: "Enter a complete email address, including a domain.",
  },
  {
    name: "Success",
    label: "Invite code",
    labelProps: {},
    inputProps: { type: "text", defaultValue: "NWT-2026-8841", "data-state": "success" },
    help: "Codes are validated against the active invitation.",
    success: "Invite code accepted.",
  },
]

const tokenMap = [
  { slot: "Label", tokens: ["--foreground-strong", "--text-caption", "--font-weight-medium"] },
  { slot: "Helper", tokens: ["--muted-foreground", "--font-weight-regular"] },
  { slot: "Error", tokens: ["--destructive"] },
  { slot: "Success", tokens: ["--success"] },
  { slot: "Disabled", tokens: ["--opacity-disabled"] },
  { slot: "Spacing", tokens: ["--space-2", "--space-4"] },
] as const

export default function LabelPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Label</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Seven field-level label states with required marker, control slot, helper, and validation
          anatomy. The control owns its chrome; the label owns labeling and state coordination.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="states-heading">
        <h2 className="mb-2 text-xl" id="states-heading">
          Complete field state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Derived label states mirrored via data-state attributes; the disabled card also wires a
          real disabled control.
        </p>

        <div className="grid max-w-[560px] gap-4">
          {states.map((state, index) => {
            const controlId = `label-demo-${index}`
            const helpId = `${controlId}-help`
            const messageId = `${controlId}-message`
            return (
              <article
                className="grid gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6"
                key={state.name}
              >
                <span className="block text-primary text-xs uppercase">{state.name}</span>
                <div className="grid gap-[var(--space-2)]">
                  <Label htmlFor={controlId} {...state.labelProps}>
                    {state.label} <LabelRequired>*</LabelRequired>
                  </Label>
                  <Input
                    aria-describedby={
                      state.error || state.success ? `${helpId} ${messageId}` : helpId
                    }
                    id={controlId}
                    required
                    {...state.inputProps}
                  />
                  <p className="m-0 text-caption text-muted-foreground" id={helpId}>
                    {state.help}
                  </p>
                  {state.error && (
                    <p
                      className="m-0 text-caption font-medium text-destructive"
                      id={messageId}
                      role="alert"
                    >
                      {state.error}
                    </p>
                  )}
                  {state.success && (
                    <p
                      className="m-0 text-caption font-medium text-success"
                      id={messageId}
                      role="status"
                    >
                      {state.success}
                    </p>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-2 text-xl" id="mapping-heading">
          Token map
        </h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          {tokenMap.map((entry) => (
            <article
              className="grid gap-2 rounded-[var(--radius-lg)] border border-border bg-card p-6"
              key={entry.slot}
            >
              <p className="m-0 text-caption font-medium text-foreground-strong">{entry.slot}</p>
              <p className="m-0 grid gap-1 text-caption text-muted-foreground">
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
