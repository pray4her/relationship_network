"use client"

import { useActionState, useEffect, useRef } from "react"
import { toast } from "sonner"

import type { MemberActionState } from "@/app/actions/members"
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

type RevokeInvitationButtonProps = {
  readonly action: (state: MemberActionState, formData: FormData) => Promise<MemberActionState>
  readonly invitationId: string
}

export function RevokeInvitationButton({ action, invitationId }: RevokeInvitationButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })
  const wasPending = useRef(false)

  useEffect(() => {
    if (wasPending.current && !isPending && state.formError === null) {
      toast.success("邀请已撤销")
    }
    wasPending.current = isPending
  }, [isPending, state.formError])

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button size="sm" type="button" variant="secondary" disabled={isPending}>
              撤销
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>撤销邀请</AlertDialogTitle>
            <AlertDialogDescription>
              撤销后该邀请链接将立即失效，被邀请人无法再凭此链接加入租户。确定要撤销吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <form action={formAction}>
              <input name="invitation_id" type="hidden" value={invitationId} />
              <AlertDialogAction type="submit" variant="destructive" pending={isPending}>
                撤销
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
