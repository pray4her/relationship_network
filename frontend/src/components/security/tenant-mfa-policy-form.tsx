"use client"

import { useActionState } from "react"

import type { TenantMfaPolicyFormState } from "@/app/actions/mfa"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
    <div className="flex flex-col gap-4">
      {state.notice ? (
        <Alert role="status">
          <AlertDescription>{state.notice}</AlertDescription>
        </Alert>
      ) : null}
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
      <p className="text-sm text-muted-foreground">
        开启后，所有未启用两步验证的成员将无法访问租户数据，直到完成 MFA 设置。
        {state.required === null
          ? ""
          : state.required
            ? "当前状态：已开启。"
            : "当前状态：已关闭。"}
      </p>
      <div className="flex flex-wrap gap-2">
        <form action={formAction}>
          <input name="required" type="hidden" value="true" />
          <Button type="submit" disabled={isPending}>
            {isPending ? "提交中…" : "开启强制 MFA"}
          </Button>
        </form>
        <form action={formAction}>
          <input name="required" type="hidden" value="false" />
          <Button type="submit" variant="secondary" disabled={isPending}>
            {isPending ? "提交中…" : "关闭强制 MFA"}
          </Button>
        </form>
      </div>
    </div>
  )
}
