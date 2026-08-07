"use client"

import { useActionState } from "react"

import type { JobActionState } from "@/app/actions/jobs"
import { Button } from "@/components/ui/button"

type JobActivateButtonProps = {
  readonly action: (state: JobActionState, formData: FormData) => Promise<JobActionState>
  readonly jobId: string
}

export function JobActivateButton({ action, jobId }: JobActivateButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <div className="flex flex-col items-start gap-2">
      <form action={formAction}>
        <input name="job_id" type="hidden" value={jobId} />
        <Button type="submit" disabled={isPending}>
          {isPending ? "启用中…" : "启用职位"}
        </Button>
      </form>
      {state.formError ? (
        <p className="text-sm text-destructive" role="alert">
          {state.formError}
        </p>
      ) : null}
    </div>
  )
}
