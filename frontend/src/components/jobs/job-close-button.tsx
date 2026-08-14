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

type JobCloseButtonProps = {
  readonly action: (state: JobActionState, formData: FormData) => Promise<JobActionState>
  readonly jobId: string
}

export function JobCloseButton({ action, jobId }: JobCloseButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button type="button" variant="secondary" pending={isPending}>
              {isPending ? "关闭中…" : "关闭职位"}
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>关闭职位</AlertDialogTitle>
            <AlertDialogDescription>
              关闭后职位释放活跃额度，可再次启用；期间不能再编辑或上传材料。确定要关闭职位吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <form action={formAction}>
              <input name="job_id" type="hidden" value={jobId} />
              <AlertDialogAction type="submit" pending={isPending}>
                {isPending ? "关闭中…" : "关闭职位"}
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
