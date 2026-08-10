import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogBody,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

/**
 * AlertDialog 预览页 —— 对应 showcase/dialog.html 的 confirmation /
 * destructive confirmation 两列(本组件只承载模态确认场景,standard 由 Dialog 负责)。
 * 首个样品 defaultOpen,静态截图即可看到 overlay + surface + 完整解剖;
 * 焦点镜像经 Button 的 data-state="focus-visible" 渲染(见 ui/button.tsx)。
 * 其余场景以 trigger 呈现,点击可交互验证。
 */
export default function AlertDialogPreviewPage() {
  return (
    <main className="mx-auto max-w-[1200px] px-6">
      <header className="border-border border-b py-16 pb-8">
        <span className="mb-3 block text-primary text-xs uppercase">Component</span>
        <h1 className="text-3xl">AlertDialog</h1>
        <p className="mt-4 max-w-xl text-foreground-body">
          Modal confirmation scenarios from the Dialog spec — confirmation and destructive
          confirmation across sm / md / lg. The first sample renders open for static capture.
        </p>
      </header>

      <section className="border-border-soft border-b py-8" aria-labelledby="matrix-heading">
        <h2 className="mb-2 text-xl" id="matrix-heading">
          Confirmation scenarios
        </h2>
        <p className="mb-6 max-w-xl text-muted-foreground text-sm">
          Every card is a live modal: role=&quot;alertdialog&quot;, focus trap, Escape to close, no
          overlay dismissal. Sizes map default→md, plus spec sm / lg; destructive adds the
          destructive surface border and title color.
        </p>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Confirmation · md · default open</h3>
            <AlertDialog defaultOpen>
              <AlertDialogTrigger render={<Button>Publish job…</Button>} />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Publish this job?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Candidates will be able to discover it.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogBody>
                  <p>Review the title, location, and application materials before publishing.</p>
                </AlertDialogBody>
                <AlertDialogFooter>
                  <AlertDialogCancel data-state="focus-visible">Keep draft</AlertDialogCancel>
                  <AlertDialogAction>Publish job</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <p className="text-muted-foreground text-xs">
              Initial focus on the safe action (focus-visible mirror via data-state)
            </p>
          </article>

          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Destructive confirmation · md</h3>
            <AlertDialog>
              <AlertDialogTrigger render={<Button variant="destructive">Delete company…</Button>} />
              <AlertDialogContent variant="destructive">
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete company?</AlertDialogTitle>
                  <AlertDialogDescription>This operation cannot be undone.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogBody>
                  <p>Company details and private documents will no longer be available.</p>
                </AlertDialogBody>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction variant="destructive">Delete company</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <p className="text-muted-foreground text-xs">
              Destructive border + title; committing action uses the destructive Button
            </p>
          </article>

          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Confirmation · sm</h3>
            <AlertDialog>
              <AlertDialogTrigger render={<Button variant="secondary">Submit order…</Button>} />
              <AlertDialogContent size="sm">
                <AlertDialogHeader>
                  <AlertDialogTitle>Submit the order?</AlertDialogTitle>
                  <AlertDialogDescription>
                    The offline order will enter review.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogBody>
                  <p>Confirm the plan, amount, and tenant before submitting the order.</p>
                </AlertDialogBody>
                <AlertDialogFooter>
                  <AlertDialogCancel size="sm">Review again</AlertDialogCancel>
                  <AlertDialogAction size="sm">Submit order</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <p className="text-muted-foreground text-xs">
              Compact padding; title and body step down one type size
            </p>
          </article>

          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Destructive · sm · disabled action</h3>
            <AlertDialog>
              <AlertDialogTrigger render={<Button variant="secondary">Remove member…</Button>} />
              <AlertDialogContent size="sm" variant="destructive">
                <AlertDialogHeader>
                  <AlertDialogTitle>Remove member?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This member will immediately lose tenant access.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogBody>
                  <p>The tenant owner cannot be removed. Choose another member to continue.</p>
                </AlertDialogBody>
                <AlertDialogFooter>
                  <AlertDialogCancel size="sm">Cancel</AlertDialogCancel>
                  <AlertDialogAction disabled size="sm" variant="destructive">
                    Remove member
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <p className="text-muted-foreground text-xs">
              Disabled committing action at --opacity-disabled
            </p>
          </article>

          <article className="grid justify-items-start gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-6">
            <h3 className="text-base font-medium">Destructive · lg · loading action</h3>
            <AlertDialog>
              <AlertDialogTrigger
                render={<Button variant="destructive">Cancel subscription…</Button>}
              />
              <AlertDialogContent size="lg" variant="destructive">
                <AlertDialogHeader>
                  <AlertDialogTitle>Cancel subscription?</AlertDialogTitle>
                  <AlertDialogDescription>
                    The tenant becomes read-only when the subscription expires.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogBody>
                  <p>
                    Members can still read existing records, but write operations will be
                    unavailable.
                  </p>
                </AlertDialogBody>
                <AlertDialogFooter>
                  <AlertDialogCancel size="lg">Keep subscription</AlertDialogCancel>
                  <AlertDialogAction loading size="lg" variant="destructive">
                    Cancel subscription
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <p className="text-muted-foreground text-xs">
              Loading contract via Button: disabled + aria-busy + centered spinner
            </p>
          </article>
        </div>
      </section>

      <section className="py-8" aria-labelledby="mapping-heading">
        <h2 className="mb-2 text-xl" id="mapping-heading">
          Spec mapping
        </h2>
        <p className="max-w-xl text-muted-foreground text-sm">
          AlertDialog renders the spec&apos;s confirmation variant (role=&quot;alertdialog&quot;,
          overlay click does not dismiss). size default→md; sm and lg follow the spec spacing scale.
          variant=&quot;destructive&quot; colors the surface border and title with --destructive.
          Lifecycle frames (half opacity + --space-2 travel, closing at --duration-fast) are driven
          by Base UI starting/ending styles.
        </p>
      </section>
    </main>
  )
}
