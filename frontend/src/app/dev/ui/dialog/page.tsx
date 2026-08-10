"use client"

import { XIcon } from "lucide-react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  dialogCloseVariants,
  dialogContentVariants,
  dialogOverlayVariants,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"

/**
 * Dialog 预览页 —— 对应 showcase/dialog.html:
 * 3 size × 3 variant 状态矩阵 + 生命周期四帧 + 真实交互示例。
 *
 * 静态展板:多个 modal popup 无法共存于同一视口,矩阵/生命周期帧用组件导出的
 * cva(dialogContentVariants / dialogOverlayVariants / dialogCloseVariants)在
 * Dialog.Root 上下文内静态渲染,状态经 data-[state=*] 镜像(见 ui/dialog.tsx 注释);
 * 语义示例走下方的 live 区。
 */

type PlateSize = "default" | "sm" | "lg"
type PlateVariant = "default" | "confirmation" | "destructive"
type PlateState = "open" | "opening" | "closing"

function DialogPlate({
  size = "default",
  variant = "default",
  state = "open",
  compact = false,
  showCloseButton = true,
  focusCloseButton = false,
  title,
  description,
  body,
  footer,
}: {
  size?: PlateSize
  variant?: PlateVariant
  state?: PlateState
  /** 生命周期帧:沿用 showcase 的紧凑 padding 与矮展板。 */
  compact?: boolean
  showCloseButton?: boolean
  focusCloseButton?: boolean
  title: string
  description: string
  body: string
  footer?: ReactNode
}) {
  return (
    <Dialog>
      <div
        aria-hidden="true"
        className={cn(
          "relative grid place-items-center overflow-hidden rounded-[var(--radius-lg)]",
          compact ? "min-h-[calc(var(--space-24)*3)]" : "min-h-[calc(var(--space-24)*5)]",
        )}
      >
        <div className={cn(dialogOverlayVariants(), "absolute")} data-state={state} />
        <div
          className={cn(
            dialogContentVariants({ size, variant }),
            "absolute max-h-none w-[calc(100%-var(--space-4)*2)]",
          )}
          data-size={size}
          data-state={state}
          data-variant={variant}
        >
          <DialogHeader className={compact ? "p-[var(--space-4)]" : undefined}>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          {showCloseButton && (
            <DialogClose
              render={
                <Button
                  className={dialogCloseVariants()}
                  data-state={focusCloseButton ? "focus-visible" : undefined}
                  size="icon"
                  tabIndex={-1}
                  variant="ghost"
                />
              }
            >
              <XIcon />
              <span className="sr-only">Close</span>
            </DialogClose>
          )}
          <DialogBody className={compact ? "p-[var(--space-4)]" : undefined}>
            <p>{body}</p>
          </DialogBody>
          {footer}
        </div>
      </div>
    </Dialog>
  )
}

type MatrixAction = {
  label: string
  variant?: "default" | "secondary" | "destructive"
  focus?: boolean
  disabled?: boolean
  loading?: boolean
}

type MatrixCell = {
  variant: PlateVariant
  label: string
  note: string
  title: string
  description: string
  body: string
  focusCloseButton?: boolean
  actions: readonly MatrixAction[]
}

type MatrixRow = {
  size: PlateSize
  label: string
  note: string
  buttonSize: "sm" | "default" | "lg"
  cells: readonly MatrixCell[]
}

const matrix: readonly MatrixRow[] = [
  {
    size: "sm",
    label: "Small",
    note: "max-width calc(--space-16 × 6) · compact padding · sm Buttons",
    buttonSize: "sm",
    cells: [
      {
        variant: "default",
        label: "Standard",
        note: "initial focus → primary",
        title: "Edit company",
        description: "Update the profile shared by tenant members.",
        body: "Changes become visible to every member with access to this company.",
        actions: [
          { label: "Cancel", variant: "secondary" },
          { label: "Save changes", variant: "default", focus: true },
        ],
      },
      {
        variant: "confirmation",
        label: "Confirmation",
        note: "initial focus → safe action",
        title: "Publish this job?",
        description: "Candidates will be able to discover it.",
        body: "Review the title, location, and application materials before publishing.",
        actions: [
          { label: "Keep draft", variant: "secondary", focus: true },
          { label: "Publish job", variant: "default" },
        ],
      },
      {
        variant: "destructive",
        label: "Destructive confirmation",
        note: "disabled destructive action",
        title: "Remove member?",
        description: "This member will immediately lose tenant access.",
        body: "The tenant owner cannot be removed. Choose another member to continue.",
        actions: [
          { label: "Cancel", variant: "secondary" },
          { label: "Remove member", variant: "destructive", disabled: true },
        ],
      },
    ],
  },
  {
    size: "default",
    label: "Medium",
    note: "max-width calc(--space-16 × 8) · default padding · md Buttons",
    buttonSize: "default",
    cells: [
      {
        variant: "default",
        label: "Standard",
        note: "focused close IconButton",
        title: "Invite a member",
        description: "Send an invitation and assign a tenant role.",
        body: "The invitee receives an email and joins after accepting the invitation.",
        focusCloseButton: true,
        actions: [
          { label: "Cancel", variant: "secondary" },
          { label: "Send invite", variant: "default" },
        ],
      },
      {
        variant: "confirmation",
        label: "Confirmation",
        note: "focused primary action",
        title: "Submit the order?",
        description: "The offline order will enter review.",
        body: "Confirm the plan, amount, and tenant before submitting the order.",
        actions: [
          { label: "Review again", variant: "secondary" },
          { label: "Submit order", variant: "default", focus: true },
        ],
      },
      {
        variant: "destructive",
        label: "Destructive confirmation",
        note: "focused destructive action",
        title: "Delete company?",
        description: "This operation cannot be undone.",
        body: "Company details and private documents will no longer be available.",
        actions: [
          { label: "Cancel", variant: "secondary" },
          { label: "Delete company", variant: "destructive", focus: true },
        ],
      },
    ],
  },
  {
    size: "lg",
    label: "Large",
    note: "max-width calc(--space-16 × 12) · spacious padding · lg Buttons",
    buttonSize: "lg",
    cells: [
      {
        variant: "default",
        label: "Standard",
        note: "loading primary action",
        title: "Upload company documents",
        description: "Files remain private and downloads stay authenticated.",
        body: "Selected documents are validated before they are stored in the private object bucket.",
        actions: [
          { label: "Cancel", variant: "secondary" },
          { label: "Upload documents", variant: "default", loading: true },
        ],
      },
      {
        variant: "confirmation",
        label: "Confirmation",
        note: "initial focus → secondary",
        title: "Enable two-step verification?",
        description: "Future sign-ins will require a time-based code.",
        body: "Store recovery information safely before enabling two-step verification.",
        actions: [
          { label: "Not now", variant: "secondary", focus: true },
          { label: "Enable", variant: "default" },
        ],
      },
      {
        variant: "destructive",
        label: "Destructive confirmation",
        note: "loading destructive action",
        title: "Cancel subscription?",
        description: "The tenant becomes read-only when the subscription expires.",
        body: "Members can still read existing records, but write operations will be unavailable.",
        actions: [
          { label: "Keep subscription", variant: "secondary" },
          { label: "Cancel subscription", variant: "destructive", loading: true },
        ],
      },
    ],
  },
]

function MatrixCellFooter({ row, cell }: { row: MatrixRow; cell: MatrixCell }) {
  return (
    <DialogFooter>
      {cell.actions.map((action) => (
        <Button
          data-state={action.focus ? "focus-visible" : undefined}
          disabled={action.disabled ?? false}
          key={action.label}
          loading={action.loading ?? false}
          size={row.buttonSize}
          tabIndex={-1}
          variant={action.variant ?? "default"}
        >
          {action.label}
        </Button>
      ))}
    </DialogFooter>
  )
}

export default function DialogPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Dialog / Modal</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Native modal semantics with explicit focus management. The matrix renders every size and
          variant together; the lifecycle band makes closed, opening, open, and closing frames
          visible.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          State matrix — sizes × variants × focus states
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Columns are standard, confirmation, and destructive confirmation. Rows are sm, md, and lg.
          Static plates are hidden from assistive technology; states are mirrored via data-state
          attributes.
        </p>

        <div className="grid gap-8">
          {matrix.map((row) => (
            <section className="grid gap-3" key={row.size} aria-label={row.label}>
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h3 className="text-base font-medium">{row.label}</h3>
                <span className="text-caption-foreground text-xs">{row.note}</span>
              </div>
              <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
                {row.cells.map((cell) => (
                  <div className="grid min-w-0 gap-2" key={cell.variant}>
                    <div className="flex flex-wrap justify-between gap-2 text-muted-foreground text-xs">
                      <span>{cell.label}</span>
                      <span>{cell.note}</span>
                    </div>
                    <DialogPlate
                      body={cell.body}
                      description={cell.description}
                      focusCloseButton={cell.focusCloseButton ?? false}
                      footer={<MatrixCellFooter cell={cell} row={row} />}
                      size={row.size}
                      title={cell.title}
                      variant={cell.variant}
                    />
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
        <p className="mt-6 max-w-xl text-muted-foreground text-xs">
          Destructive confirmation colors the surface border and title with --destructive; focus
          treatment stays the shared --ring-width / --ring-focus recipe across all variants.
        </p>
      </section>

      <section className="border-border-soft border-b py-8" aria-labelledby="lifecycle-heading">
        <h2 className="mb-2 text-xl" id="lifecycle-heading">
          Lifecycle — closed · opening · open · closing
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Opening and closing are shown at the --opacity-disabled midpoint and --space-2 travel;
          open is fully settled.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
          <div className="grid gap-2">
            <span className="text-muted-foreground text-xs">Closed reference</span>
            <div className="grid min-h-[calc(var(--space-24)*3)] place-items-center rounded-[var(--radius-lg)] border border-border bg-surface-soft p-[var(--space-4)]">
              <Button aria-expanded="false" variant="secondary">
                Open dialog
              </Button>
            </div>
          </div>
          <div className="grid gap-2">
            <span className="text-muted-foreground text-xs">Opening · --duration-normal</span>
            <DialogPlate
              body="Opacity and travel are token-driven."
              compact
              description="Initial focus moves as the modal opens."
              showCloseButton={false}
              state="opening"
              title="Opening"
            />
          </div>
          <div className="grid gap-2">
            <span className="text-muted-foreground text-xs">Open · focus trapped</span>
            <DialogPlate
              body="Background interaction is unavailable."
              compact
              description="Surface is settled at full opacity."
              footer={
                <DialogFooter className="px-[var(--space-4)] py-[var(--space-3)]">
                  <Button size="sm" tabIndex={-1}>
                    Continue
                  </Button>
                </DialogFooter>
              }
              showCloseButton={false}
              title="Open"
            />
          </div>
          <div className="grid gap-2">
            <span className="text-muted-foreground text-xs">Closing · --duration-fast</span>
            <DialogPlate
              body="The native dialog then leaves the top layer."
              compact
              description="Focus returns after the exit lands."
              showCloseButton={false}
              state="closing"
              title="Closing"
            />
          </div>
        </div>
      </section>

      <section className="py-8" aria-labelledby="live-heading">
        <h2 className="mb-2 text-xl" id="live-heading">
          Live — modality, focus trap, Escape, and focus return
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Confirmation and destructive dialogs disable pointer dismissal (disablePointerDismissal),
          preserving the explicit decision; all three still close on Escape and return focus to the
          trigger.
        </p>

        <div className="flex flex-wrap gap-[var(--space-3)]">
          <Dialog>
            <DialogTrigger render={<Button variant="secondary">Open standard</Button>} />
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Edit company</DialogTitle>
                <DialogDescription>Update the profile shared by tenant members.</DialogDescription>
              </DialogHeader>
              <DialogBody>
                <p>Changes become visible to every member with access to this company.</p>
              </DialogBody>
              <DialogFooter>
                <DialogClose render={<Button variant="secondary">Cancel</Button>} />
                <DialogClose render={<Button>Save changes</Button>} />
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog disablePointerDismissal>
            <DialogTrigger render={<Button>Open confirmation</Button>} />
            <DialogContent variant="confirmation">
              <DialogHeader>
                <DialogTitle>Publish this job?</DialogTitle>
                <DialogDescription>Candidates will be able to discover it.</DialogDescription>
              </DialogHeader>
              <DialogBody>
                <p>Review the title, location, and application materials before publishing.</p>
              </DialogBody>
              <DialogFooter>
                <DialogClose render={<Button variant="secondary">Keep draft</Button>} />
                <DialogClose render={<Button>Publish job</Button>} />
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog disablePointerDismissal>
            <DialogTrigger render={<Button variant="destructive">Open destructive</Button>} />
            <DialogContent variant="destructive">
              <DialogHeader>
                <DialogTitle>Delete company?</DialogTitle>
                <DialogDescription>This operation cannot be undone.</DialogDescription>
              </DialogHeader>
              <DialogBody>
                <p>Company details and private documents will no longer be available.</p>
              </DialogBody>
              <DialogFooter>
                <DialogClose render={<Button variant="secondary">Cancel</Button>} />
                <DialogClose render={<Button variant="destructive">Delete company</Button>} />
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </section>
    </main>
  )
}
