import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertDismiss,
  AlertTitle,
} from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

/**
 * Alert 预览页 —— 对应 showcase/alert.html:
 * 内部控件状态矩阵(dismiss + 组合 Button)+ 5 个语义变体的完整解剖。
 * 状态经 data-[state=*] 镜像静态渲染(见 ui/alert.tsx 与 ui/button.tsx 注释)。
 */
const dismissIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path d="m7 7 10 10M17 7 7 17" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const neutralIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.5" stroke="currentColor" />
    <path d="M8 12h8" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const infoIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.5" stroke="currentColor" />
    <path d="M12 11v5" stroke="currentColor" strokeLinecap="round" />
    <circle cx="12" cy="8" fill="currentColor" r="0.5" />
  </svg>
)

const successIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.5" stroke="currentColor" />
    <path
      d="m8 12.5 2.5 2.5L16 9.5"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const warningIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <path
      d="M10.3 4.3 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M12 9v4" stroke="currentColor" strokeLinecap="round" />
    <path d="M12 17h.01" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const destructiveIcon = (
  <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.5" stroke="currentColor" />
    <path d="m9 9 6 6M15 9l-6 6" stroke="currentColor" strokeLinecap="round" />
  </svg>
)

const controlStates = [
  { label: "Default", buttonProps: {}, dismissProps: {} },
  {
    label: "Hover",
    buttonProps: { "data-state": "hover", tabIndex: -1 },
    dismissProps: { "data-state": "hover", tabIndex: -1 },
  },
  {
    label: "Active",
    buttonProps: { "data-state": "active", tabIndex: -1 },
    dismissProps: { "data-state": "active", tabIndex: -1 },
  },
  {
    label: "Focus-visible",
    buttonProps: { "data-state": "focus-visible", tabIndex: -1 },
    dismissProps: { "data-state": "focus-visible", tabIndex: -1 },
  },
  {
    label: "Disabled",
    buttonProps: { disabled: true },
    dismissProps: { disabled: true },
  },
] as const

const hierarchy = [
  {
    variant: "default",
    icon: neutralIcon,
    role: "region",
    title: "Offline drafts are stored locally",
    description:
      "Changes sync when the connection returns. Neutral uses canvas text roles — no status accent.",
    action: "Open drafts",
  },
  {
    variant: "info",
    icon: infoIcon,
    role: "region",
    title: "Matching index is syncing",
    description:
      "New talent embeddings appear in search within a few minutes. Existing results stay available while the index catches up.",
    action: "View status",
  },
  {
    variant: "success",
    icon: successIcon,
    role: "status",
    title: "Invite sent",
    description: "Mei Chen will receive an email with a link to join the Acme tenant.",
    action: "View members",
  },
  {
    variant: "warning",
    icon: warningIcon,
    role: "status",
    title: "Subscription expires in 5 days",
    description: "After expiry the tenant becomes read-only until a plan is renewed.",
    action: "Renew plan",
  },
  {
    variant: "destructive",
    icon: destructiveIcon,
    role: "alert",
    title: "Document upload failed",
    description:
      "The file exceeds the 25 MB limit. Compress it or split into smaller parts, then try again.",
    action: "Try again",
  },
] as const

const actionLabelClass = "text-muted-foreground text-xs uppercase"

export default function AlertPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">Alert</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Every variant is explicit and token-driven: background, border, icon, and text all resolve
          to semantic status tokens. The static preview also exposes default, hover, active,
          focus-visible, and disabled internal controls.
        </p>
      </header>

      <section
        className="border-border-soft border-b py-8"
        aria-labelledby="control-matrix-heading"
      >
        <h2 className="mb-2 text-xl" id="control-matrix-heading">
          Internal control state matrix
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Each row keeps identical Alert anatomy while both the composed action and private dismiss
          control hold the labeled state. Hover and active use different token surfaces;
          focus-visible uses the shared ring; disabled uses the shared opacity plus native disabled
          semantics.
        </p>

        <div className="grid max-w-[42rem] gap-4">
          {controlStates.map((state) => (
            <Alert aria-label={`${state.label} internal controls`} key={state.label}>
              <AlertTitle>{state.label}</AlertTitle>
              <AlertAction>
                <Button size="sm" variant="secondary" {...state.buttonProps}>
                  Open drafts
                </Button>
              </AlertAction>
              <AlertDismiss
                aria-label={`Dismiss, ${state.label.toLowerCase()}`}
                {...state.dismissProps}
              >
                {dismissIcon}
              </AlertDismiss>
            </Alert>
          ))}
        </div>
      </section>

      <section className="py-8" aria-labelledby="hierarchy-heading">
        <h2 className="mb-2 text-xl" id="hierarchy-heading">
          Semantic state matrix — status hierarchy
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Neutral → info → success → warning → destructive in one stack. Each row carries the full
          anatomy (icon, title, description, action, dismiss). Action rows pair a default control
          with a static focus-visible twin; the dismiss control shows the same focus ring.
        </p>

        <div className="grid max-w-[42rem] gap-4">
          {hierarchy.map((item) => (
            <Alert
              aria-labelledby={`h-${item.variant}-title`}
              key={item.variant}
              role={item.role}
              variant={item.variant}
            >
              {item.icon}
              <AlertTitle id={`h-${item.variant}-title`}>{item.title}</AlertTitle>
              <AlertDescription>{item.description}</AlertDescription>
              <AlertAction>
                <span className={actionLabelClass}>Action</span>
                <Button size="sm" variant="secondary">
                  {item.action}
                </Button>
                <span className={actionLabelClass}>Focus</span>
                <Button data-state="focus-visible" size="sm" tabIndex={-1} variant="secondary">
                  {item.action}
                </Button>
              </AlertAction>
              <AlertDismiss
                aria-label={`Dismiss ${item.title.toLowerCase()} notice`}
                data-state="focus-visible"
                tabIndex={-1}
              >
                {dismissIcon}
              </AlertDismiss>
            </Alert>
          ))}
        </div>

        <p className="mt-6 max-w-xl text-muted-foreground text-xs">
          Token map per semantic variant: soft surface (--*-soft) · border / icon / title /
          description / dismiss (--info / --success / --warning / --destructive). Neutral: --card ·
          --border · --foreground / --muted-foreground. Focus rings use --ring-width / --ring-focus
          on both Button and AlertDismiss.
        </p>
      </section>
    </main>
  )
}
