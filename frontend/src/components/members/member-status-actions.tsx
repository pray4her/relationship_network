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

type MemberStatusActionsProps = {
  readonly action: (state: MemberActionState, formData: FormData) => Promise<MemberActionState>
  readonly membershipId: string
  readonly isActive: boolean
}

type Intent = "activate" | "deactivate" | "remove"

const intentSuccessMessages: Record<Intent, string> = {
  activate: "成员已启用",
  deactivate: "成员已停用",
  remove: "成员已移除",
}

export function MemberStatusActions({ action, isActive, membershipId }: MemberStatusActionsProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })
  const lastIntent = useRef<Intent | null>(null)
  const wasPending = useRef(false)

  useEffect(() => {
    if (wasPending.current && !isPending && state.formError === null && lastIntent.current) {
      toast.success(intentSuccessMessages[lastIntent.current])
      lastIntent.current = null
    }
    wasPending.current = isPending
  }, [isPending, state.formError])

  return (
    <div className="flex flex-wrap items-center gap-2">
      {isActive ? (
        <AlertDialog>
          <AlertDialogTrigger
            render={
              <Button size="sm" type="button" variant="secondary" disabled={isPending}>
                停用
              </Button>
            }
          />
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>停用成员</AlertDialogTitle>
              <AlertDialogDescription>
                停用后该成员将无法访问租户数据，你可以随时重新启用。确定要停用该成员吗？
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <form action={formAction} onSubmit={() => (lastIntent.current = "deactivate")}>
                <input name="membership_id" type="hidden" value={membershipId} />
                <input name="intent" type="hidden" value="deactivate" />
                <AlertDialogAction type="submit" variant="destructive" pending={isPending}>
                  停用
                </AlertDialogAction>
              </form>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : (
        <form action={formAction} onSubmit={() => (lastIntent.current = "activate")}>
          <input name="membership_id" type="hidden" value={membershipId} />
          <input name="intent" type="hidden" value="activate" />
          <Button size="sm" type="submit" variant="secondary" pending={isPending}>
            启用
          </Button>
        </form>
      )}
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button size="sm" type="button" variant="secondary" disabled={isPending}>
              移除
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>移除成员</AlertDialogTitle>
            <AlertDialogDescription>确定要移除该成员吗？此操作不可撤销。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <form action={formAction} onSubmit={() => (lastIntent.current = "remove")}>
              <input name="membership_id" type="hidden" value={membershipId} />
              <input name="intent" type="hidden" value="remove" />
              <AlertDialogAction type="submit" variant="destructive" pending={isPending}>
                移除
              </AlertDialogAction>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.formError ? (
        <Alert className="w-full" variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
