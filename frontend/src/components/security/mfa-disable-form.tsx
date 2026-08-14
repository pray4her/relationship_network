"use client"

import { useActionState } from "react"

import type { MfaDisableFormState } from "@/app/actions/mfa"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
      <FormField
        autoComplete="one-time-code"
        error={state.fieldErrors.code}
        hint="输入当前身份验证器验证码以停用两步验证"
        id="code"
        inputMode="numeric"
        label="当前验证码"
        maxLength={6}
        type="text"
      />
      <div>
        <Button pending={isPending} type="submit" variant="secondary">
          停用两步验证
        </Button>
      </div>
    </form>
  )
}
