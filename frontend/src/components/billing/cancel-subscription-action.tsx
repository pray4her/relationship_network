"use client"

import { useActionState } from "react"

import type { CancelSubscriptionActionState } from "@/app/actions/orders"
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
              <AlertDialogAction type="submit" variant="destructive" disabled={isPending}>
                取消订阅
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
