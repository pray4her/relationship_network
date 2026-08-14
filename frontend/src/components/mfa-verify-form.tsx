"use client"

import { useActionState, useState } from "react"

import type { MfaVerifyFormState } from "@/app/actions/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

type MfaVerifyFormProps = {
  readonly action: (state: MfaVerifyFormState, formData: FormData) => Promise<MfaVerifyFormState>
}

export function MfaVerifyForm({ action }: MfaVerifyFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })
  const [factor, setFactor] = useState<"code" | "recovery_code">("code")
  const isRecoveryCode = factor === "recovery_code"

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}

      <FieldSet>
        <FieldLegend variant="label">验证方式</FieldLegend>
        <RadioGroup
          name="factor"
          onValueChange={(value) => setFactor(value === "recovery_code" ? "recovery_code" : "code")}
          value={factor}
        >
          <label className="flex min-h-11 items-center gap-3 text-sm" htmlFor="factor-code">
            <RadioGroupItem id="factor-code" value="code" />
            身份验证器验证码
          </label>
          <label className="flex min-h-11 items-center gap-3 text-sm" htmlFor="factor-recovery">
            <RadioGroupItem id="factor-recovery" value="recovery_code" />
            恢复码
          </label>
        </RadioGroup>
      </FieldSet>

      <Field data-invalid={state.fieldErrors.code ? true : undefined}>
        <FieldLabel htmlFor="code_value">验证码或恢复码</FieldLabel>
        <Input
          aria-invalid={state.fieldErrors.code ? true : undefined}
          autoComplete="one-time-code"
          autoFocus
          id="code_value"
          inputMode={isRecoveryCode ? "text" : "numeric"}
          maxLength={isRecoveryCode ? undefined : 6}
          name="code_value"
          type="text"
        />
        <FieldDescription>输入身份验证器中的 6 位验证码，或选择恢复码后输入恢复码</FieldDescription>
        {state.fieldErrors.code ? <FieldError>{state.fieldErrors.code}</FieldError> : null}
      </Field>

      <Button className="w-full" pending={isPending} type="submit">
        验证并登录
      </Button>
    </form>
  )
}
