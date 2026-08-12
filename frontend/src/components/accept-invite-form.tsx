"use client"

import { useActionState } from "react"

import type { AcceptInvitationFormState } from "@/app/actions/invitations"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

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
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}

      <input name="token" type="hidden" value={token} />
      <Button className="w-full" disabled={isPending} type="submit">
        {isPending ? <Spinner data-icon="inline-start" /> : null}
        接受邀请
      </Button>
    </form>
  )
}
