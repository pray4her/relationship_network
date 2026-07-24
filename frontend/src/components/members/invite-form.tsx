"use client"

import { useActionState } from "react"

import type { InviteFormState } from "@/app/actions/members"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"

type InviteFormProps = {
  readonly action: (state: InviteFormState, formData: FormData) => Promise<InviteFormState>
}

export function InviteForm({ action }: InviteFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    createdInvitation: null,
    fieldErrors: {},
    formError: null,
  })

  return (
    <div className="invite-section">
      {state.createdInvitation ? (
        <div className="notice notice-info" role="status">
          <p>邀请已创建。请将此链接发送给被邀请人（链接与令牌仅显示一次）：</p>
          <p className="mono-value">{state.createdInvitation.inviteUrl}</p>
          <p>
            邀请令牌：<span className="mono-value">{state.createdInvitation.token}</span>
          </p>
        </div>
      ) : null}

      <form action={formAction} className="auth-form" noValidate>
        {state.formError ? (
          <p className="form-error" role="alert">
            {state.formError}
          </p>
        ) : null}

        <FormField
          autoComplete="off"
          error={state.fieldErrors.email}
          id="email"
          label="被邀请人邮箱"
          type="email"
        />

        <Button type="submit" disabled={isPending}>
          {isPending ? "创建中…" : "邀请"}
        </Button>
      </form>
    </div>
  )
}
