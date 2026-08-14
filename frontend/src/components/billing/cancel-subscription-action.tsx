"use client"

import { useActionState, useEffect, useRef } from "react"
import { toast } from "sonner"

import type { CancelSubscriptionActionState } from "@/app/actions/orders"
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

type CancelSubscriptionActionProps = {
  readonly action: (
    state: CancelSubscriptionActionState,
    formData: FormData,
  ) => Promise<CancelSubscriptionActionState>
}

export function CancelSubscriptionAction({ action }: CancelSubscriptionActionProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })
  const wasPending = useRef(false)

  useEffect(() => {
    if (wasPending.current && !isPending && state.formError === null) {
      toast.success("已申请取消订阅，将在当前周期结束后生效")
    }
    wasPending.current = isPending
  }, [isPending, state.formError])

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button size="sm" type="button" variant="secondary" disabled={isPending}>
              取消订阅
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>取消订阅</AlertDialogTitle>
            <AlertDialogDescription>
              确定要取消订阅吗？取消将在当前有效期结束后生效。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>返回</AlertDialogCancel>
            <form action={formAction}>
              <AlertDialogAction type="submit" variant="destructive" pending={isPending}>
                取消订阅
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
