"use client"

import { useActionState } from "react"

import type { MemberActionState } from "@/app/actions/members"
import { Button } from "@/components/ui/button"

type RevokeInvitationButtonProps = {
  readonly action: (state: MemberActionState, formData: FormData) => Promise<MemberActionState>
  readonly invitationId: string
}

export function RevokeInvitationButton({ action, invitationId }: RevokeInvitationButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <form action={formAction} className="table-actions">
      <input name="invitation_id" type="hidden" value={invitationId} />
      <Button className="btn-small" mode="secondary" type="submit" disabled={isPending}>
        撤销
      </Button>
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}
    </form>
  )
}
