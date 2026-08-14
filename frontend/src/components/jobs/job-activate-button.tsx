"use client"

import { useActionState } from "react"

import type { JobActionState } from "@/app/actions/jobs"
import { Alert, AlertDescription } from "@/components/ui/alert"
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

type JobActivateButtonProps = {
  readonly action: (state: JobActionState, formData: FormData) => Promise<JobActionState>
  readonly jobId: string
}

export function JobActivateButton({ action, jobId }: JobActivateButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button type="button" pending={isPending}>
              启用职位
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>启用职位</AlertDialogTitle>
            <AlertDialogDescription>
              启用后职位进入匹配范围并占用活跃额度；期间不能再编辑或上传材料。确定要启用职位吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <form action={formAction}>
              <input name="job_id" type="hidden" value={jobId} />
              <AlertDialogAction type="submit" pending={isPending}>
                {isPending ? "启用中…" : "启用职位"}
              </AlertDialogAction>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
