"use client"

import { useActionState } from "react"

import type { TenantMfaPolicyFormState } from "@/app/actions/mfa"
import { Button } from "@/components/ui/button"

type TenantMfaPolicyFormProps = {
  readonly action: (
    state: TenantMfaPolicyFormState,
    formData: FormData,
  ) => Promise<TenantMfaPolicyFormState>
}

export function TenantMfaPolicyForm({ action }: TenantMfaPolicyFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    formError: null,
    notice: null,
    required: null,
  })

  return (
    <div className="mfa-step">
      {state.notice ? (
        <p className="notice notice-info" role="status">
          {state.notice}
        </p>
      ) : null}
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}
      <p className="field-hint">
        开启后，所有未启用两步验证的成员将无法访问租户数据，直到完成 MFA 设置。
        {state.required === null
          ? ""
          : state.required
            ? "当前状态：已开启。"
            : "当前状态：已关闭。"}
      </p>
      <div className="table-actions">
        <form action={formAction}>
          <input name="required" type="hidden" value="true" />
          <Button type="submit" disabled={isPending}>
            {isPending ? "提交中…" : "开启强制 MFA"}
          </Button>
        </form>
        <form action={formAction}>
          <input name="required" type="hidden" value="false" />
          <Button mode="secondary" type="submit" disabled={isPending}>
            {isPending ? "提交中…" : "关闭强制 MFA"}
          </Button>
        </form>
      </div>
    </div>
  )
}
