"use client"

import { useActionState } from "react"

import type { CancelSubscriptionActionState } from "@/app/actions/orders"
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
    <div className="table-actions">
      <form
        action={formAction}
        onSubmit={(event) => {
          if (!window.confirm("确定要取消订阅吗？取消将在当前有效期结束后生效。")) {
            event.preventDefault()
          }
        }}
      >
        <Button className="btn-small" mode="secondary" type="submit" disabled={isPending}>
          取消订阅
        </Button>
      </form>
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}
    </div>
  )
}
