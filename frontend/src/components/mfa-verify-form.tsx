"use client"

import { useActionState } from "react"

import type { MfaVerifyFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"

type MfaVerifyFormProps = {
  readonly action: (state: MfaVerifyFormState, formData: FormData) => Promise<MfaVerifyFormState>
}

export function MfaVerifyForm({ action }: MfaVerifyFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })

  return (
    <form action={formAction} className="auth-form" noValidate>
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}

      <fieldset className="radio-row">
        <legend className="field-label">验证方式</legend>
        <label className="radio-option" htmlFor="factor-code">
          <input defaultChecked id="factor-code" name="factor" type="radio" value="code" />
          身份验证器验证码
        </label>
        <label className="radio-option" htmlFor="factor-recovery">
          <input id="factor-recovery" name="factor" type="radio" value="recovery_code" />
          恢复码
        </label>
      </fieldset>

      <FormField
        autoComplete="one-time-code"
        error={state.fieldErrors.code}
        hint="输入身份验证器中的 6 位验证码，或选择恢复码后输入恢复码"
        id="code_value"
        label="验证码或恢复码"
        type="text"
      />

      <Button type="submit" disabled={isPending}>
        {isPending ? "验证中…" : "验证并登录"}
      </Button>
    </form>
  )
}
