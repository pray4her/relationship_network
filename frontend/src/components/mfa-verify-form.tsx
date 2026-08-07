"use client"

import { useActionState } from "react"

import type { MfaVerifyFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { FieldLegend, FieldSet } from "@/components/ui/field"

type MfaVerifyFormProps = {
  readonly action: (state: MfaVerifyFormState, formData: FormData) => Promise<MfaVerifyFormState>
}

export function MfaVerifyForm({ action }: MfaVerifyFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}

      <FieldSet>
        <FieldLegend variant="label">验证方式</FieldLegend>
        <label className="flex items-center gap-2 text-sm" htmlFor="factor-code">
          <input
            className="size-4 accent-primary"
            defaultChecked
            id="factor-code"
            name="factor"
            type="radio"
            value="code"
          />
          身份验证器验证码
        </label>
        <label className="flex items-center gap-2 text-sm" htmlFor="factor-recovery">
          <input
            className="size-4 accent-primary"
            id="factor-recovery"
            name="factor"
            type="radio"
            value="recovery_code"
          />
          恢复码
        </label>
      </FieldSet>

      <FormField
        autoComplete="one-time-code"
        error={state.fieldErrors.code}
        hint="输入身份验证器中的 6 位验证码，或选择恢复码后输入恢复码"
        id="code_value"
        label="验证码或恢复码"
        type="text"
      />

      <Button className="w-full" disabled={isPending} type="submit">
        {isPending ? "验证中…" : "验证并登录"}
      </Button>
    </form>
  )
}
