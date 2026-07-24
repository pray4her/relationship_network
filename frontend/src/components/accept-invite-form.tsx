"use client"

import { useActionState } from "react"

import type { AcceptInvitationFormState } from "@/app/actions/invitations"
import { Button } from "@/components/ui/button"

type AcceptInviteFormProps = {
  readonly action: (
    state: AcceptInvitationFormState,
    formData: FormData,
  ) => Promise<AcceptInvitationFormState>
  readonly token: string
}

export function AcceptInviteForm({ action, token }: AcceptInviteFormProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <form action={formAction} className="auth-form" noValidate>
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}

      <input name="token" type="hidden" value={token} />
      <Button type="submit" disabled={isPending}>
        {isPending ? "接受中…" : "接受邀请"}
      </Button>
    </form>
  )
}
