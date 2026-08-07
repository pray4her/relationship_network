"use client"

import { useActionState } from "react"

import type { JobActionState } from "@/app/actions/jobs"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

type JobArchiveButtonProps = {
  readonly action: (state: JobActionState, formData: FormData) => Promise<JobActionState>
  readonly jobId: string
}

export function JobArchiveButton({ action, jobId }: JobArchiveButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button type="button" variant="secondary" disabled={isPending}>
              {isPending ? "归档中…" : "归档职位"}
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>归档职位</AlertDialogTitle>
            <AlertDialogDescription>
              归档为终态，职位将变为只读且不能再启用。启用中的职位需先关闭。确定要归档职位吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <form action={formAction}>
              <input name="job_id" type="hidden" value={jobId} />
              <AlertDialogAction type="submit" variant="destructive" disabled={isPending}>
                {isPending ? "归档中…" : "归档职位"}
              </AlertDialogAction>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.formError ? (
        <p className="text-sm text-destructive" role="alert">
          {state.formError}
        </p>
      ) : null}
    </div>
  )
}
