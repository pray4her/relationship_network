"use client"

import { useActionState, useEffect, useId, useRef, useState } from "react"
import { toast } from "sonner"

import type { TenantStatusActionState } from "@/app/actions/admin"
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
import type { TenantStatus } from "@/lib/admin-contract"

type TenantStatusActionProps = {
  readonly action: (
    state: TenantStatusActionState,
    formData: FormData,
  ) => Promise<TenantStatusActionState>
  readonly tenantId: string
  readonly status: TenantStatus
}

export function TenantStatusAction({ action, status, tenantId }: TenantStatusActionProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })
  const [open, setOpen] = useState(false)
  const submitted = useRef(false)
  const formId = useId()
  const suspend = status === "active"

  useEffect(() => {
    if (isPending) {
      submitted.current = true
      return
    }
    if (!submitted.current) return
    submitted.current = false
    if (state.formError === null) {
      setOpen(false)
      toast.success(suspend ? "租户已暂停" : "租户已恢复")
    }
  }, [isPending, state.formError, suspend])

  return (
    <div className="flex flex-wrap items-center gap-2">
      <form action={formAction} id={formId}>
        <input name="tenant_id" type="hidden" value={tenantId} />
        <input name="intent" type="hidden" value={suspend ? "suspend" : "reactivate"} />
      </form>
      <AlertDialog onOpenChange={setOpen} open={open}>
        <AlertDialogTrigger render={<Button disabled={isPending} size="sm" variant="secondary" />}>
          {suspend ? "暂停" : "恢复"}
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{suspend ? "暂停租户" : "恢复租户"}</AlertDialogTitle>
            <AlertDialogDescription>
              {suspend ? "确定要暂停该租户吗？" : "确定要恢复该租户吗？"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {state.formError !== null ? (
            <Alert variant="destructive">
              <AlertDescription>{state.formError}</AlertDescription>
            </Alert>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              form={formId}
              pending={isPending}
              type="submit"
              variant={suspend ? "destructive" : "default"}
            >
              {suspend ? "暂停" : "恢复"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
