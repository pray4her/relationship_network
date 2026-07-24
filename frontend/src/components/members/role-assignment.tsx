"use client"

import { useActionState } from "react"

import type { MemberActionState } from "@/app/actions/members"
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

  return (
    <details className="role-editor">
      <summary>分配角色</summary>
      <form action={formAction} className="role-editor-form">
        <input name="membership_id" type="hidden" value={membershipId} />
        <div className="role-options">
          {roles.map((role) => (
            <label className="radio-option" key={role.id} htmlFor={`${membershipId}-${role.id}`}>
              <input
                defaultChecked={assignedRoleIds.includes(role.id)}
                id={`${membershipId}-${role.id}`}
                name="role_ids"
                type="checkbox"
                value={role.id}
              />
              {role.name}
              {role.description ? <span className="field-hint">{role.description}</span> : null}
            </label>
          ))}
        </div>
        <Button className="btn-small" mode="secondary" type="submit" disabled={isPending}>
          {isPending ? "保存中…" : "保存角色"}
        </Button>
        {state.formError ? (
          <p className="form-error" role="alert">
            {state.formError}
          </p>
        ) : null}
      </form>
    </details>
  )
}
