"use client"

import { useActionState, useEffect, useRef } from "react"
import { toast } from "sonner"

import type { MemberActionState } from "@/app/actions/members"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import type { RoleView } from "@/lib/members-contract"

type RoleAssignmentProps = {
  readonly action: (state: MemberActionState, formData: FormData) => Promise<MemberActionState>
  readonly membershipId: string
  readonly assignedRoleIds: readonly string[]
  readonly roles: readonly RoleView[]
}

export function RoleAssignment({
  action,
  assignedRoleIds,
  membershipId,
  roles,
}: RoleAssignmentProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })
  const wasPending = useRef(false)

  useEffect(() => {
    if (wasPending.current && !isPending && state.formError === null) {
      toast.success("角色已保存")
    }
    wasPending.current = isPending
  }, [isPending, state.formError])

  return (
    <details className="w-full max-w-md rounded-lg border px-3 py-2">
      <summary className="cursor-pointer text-sm font-medium">分配角色</summary>
      <form action={formAction} className="mt-3 flex flex-col gap-3">
        <input name="membership_id" type="hidden" value={membershipId} />
        <div className="flex flex-col gap-2">
          {roles.map((role) => (
            <label
              className="flex cursor-pointer items-start gap-2 text-sm"
              key={role.id}
              htmlFor={`${membershipId}-${role.id}`}
            >
              <input
                className="mt-1 accent-primary"
                defaultChecked={assignedRoleIds.includes(role.id)}
                id={`${membershipId}-${role.id}`}
                name="role_ids"
                type="checkbox"
                value={role.id}
              />
              <span>
                {role.name}
                {role.description ? (
                  <span className="block text-xs text-muted-foreground">{role.description}</span>
                ) : null}
              </span>
            </label>
          ))}
        </div>
        <div>
          <Button size="sm" type="submit" variant="secondary" pending={isPending}>
            保存角色
          </Button>
        </div>
        {state.formError ? (
          <Alert variant="destructive">
            <AlertDescription>{state.formError}</AlertDescription>
          </Alert>
        ) : null}
      </form>
    </details>
  )
}
