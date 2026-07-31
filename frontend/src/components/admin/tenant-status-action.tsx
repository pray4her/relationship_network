"use client"

import { useActionState } from "react"

import type { TenantStatusActionState } from "@/app/actions/admin"
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
  const suspend = status === "active"

  return (
    <div className="table-actions">
      <form
        action={formAction}
        onSubmit={(event) => {
          const message = suspend ? "确定要暂停该租户吗？" : "确定要恢复该租户吗？"
          if (!window.confirm(message)) {
            event.preventDefault()
          }
        }}
      >
        <input name="tenant_id" type="hidden" value={tenantId} />
        <input name="intent" type="hidden" value={suspend ? "suspend" : "reactivate"} />
        <Button className="btn-small" mode="secondary" type="submit" disabled={isPending}>
          {suspend ? "暂停" : "恢复"}
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
