"use client"

import { useActionState, useEffect, useRef } from "react"
import { toast } from "sonner"

import type { InviteFormState } from "@/app/actions/members"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

type InviteFormProps = {
  readonly action: (state: InviteFormState, formData: FormData) => Promise<InviteFormState>
}

const monoValueClassName =
  "w-fit rounded-md border bg-muted px-2.5 py-1.5 font-mono text-sm break-all"

export function InviteForm({ action }: InviteFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    createdInvitation: null,
    fieldErrors: {},
    formError: null,
  })
  const lastInvitation = useRef(state.createdInvitation)

  useEffect(() => {
    if (state.createdInvitation !== null && state.createdInvitation !== lastInvitation.current) {
      toast.success("邀请已创建")
    }
    lastInvitation.current = state.createdInvitation
  }, [state.createdInvitation])

  return (
    <div className="flex flex-col gap-4">
      {state.createdInvitation ? (
        <Alert role="status" variant="success">
          <AlertDescription className="flex flex-col gap-2">
            <p>邀请已创建。请将此链接发送给被邀请人（链接与令牌仅显示一次）：</p>
            <p className={monoValueClassName}>{state.createdInvitation.inviteUrl}</p>
            <p>
              邀请令牌：
              <span className="rounded-md border bg-muted px-2.5 py-1.5 font-mono text-sm break-all">
                {state.createdInvitation.token}
              </span>
            </p>
          </AlertDescription>
        </Alert>
      ) : null}

      <form action={formAction} className="flex flex-col gap-4" noValidate>
        {state.formError ? (
          <Alert variant="destructive">
            <AlertDescription>{state.formError}</AlertDescription>
          </Alert>
        ) : null}

        <FormField
          autoComplete="email"
          error={state.fieldErrors.email}
          id="email"
          label="被邀请人邮箱"
          type="email"
        />

        <div>
          <Button pending={isPending} type="submit">
            邀请
          </Button>
        </div>
      </form>
    </div>
  )
}
