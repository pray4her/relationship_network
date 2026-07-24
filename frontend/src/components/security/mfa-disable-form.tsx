"use client"

import { useActionState } from "react"

import type { MfaDisableFormState } from "@/app/actions/mfa"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"

type MfaDisableFormProps = {
  readonly action: (state: MfaDisableFormState, formData: FormData) => Promise<MfaDisableFormState>
}

export function MfaDisableForm({ action }: MfaDisableFormProps) {
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
      <FormField
        autoComplete="one-time-code"
        error={state.fieldErrors.code}
        hint="输入当前身份验证器验证码以停用两步验证"
        id="code"
        label="当前验证码"
        type="text"
      />
      <Button mode="secondary" type="submit" disabled={isPending}>
        {isPending ? "停用中…" : "停用两步验证"}
      </Button>
    </form>
  )
}
