"use client"

import { useActionState } from "react"

import type { MemberActionState } from "@/app/actions/members"
import { Button } from "@/components/ui/button"

type MemberStatusActionsProps = {
  readonly action: (state: MemberActionState, formData: FormData) => Promise<MemberActionState>
  readonly membershipId: string
  readonly isActive: boolean
}

export function MemberStatusActions({ action, isActive, membershipId }: MemberStatusActionsProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <div className="table-actions">
      <form action={formAction}>
        <input name="membership_id" type="hidden" value={membershipId} />
        <input name="intent" type="hidden" value={isActive ? "deactivate" : "activate"} />
        <Button className="btn-small" mode="secondary" type="submit" disabled={isPending}>
          {isActive ? "停用" : "启用"}
        </Button>
      </form>
      <form
        action={formAction}
        onSubmit={(event) => {
          if (!window.confirm("确定要移除该成员吗？此操作不可撤销。")) {
            event.preventDefault()
          }
        }}
      >
        <input name="membership_id" type="hidden" value={membershipId} />
        <input name="intent" type="hidden" value="remove" />
        <Button className="btn-small" mode="secondary" type="submit" disabled={isPending}>
          移除
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
