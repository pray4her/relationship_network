"use client"

import { useActionState } from "react"

import type { AuthFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

type LoginFormProps = {
  readonly action: (state: AuthFormState, formData: FormData) => Promise<AuthFormState>
}

export function LoginForm({ action }: LoginFormProps) {
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
        autoComplete="email"
        error={state.fieldErrors.email}
        id="email"
        label="邮箱"
        type="email"
      />
      <FormField
        autoComplete="current-password"
        error={state.fieldErrors.password}
        id="password"
        label="密码"
        type="password"
      />

      <Button className="w-full" disabled={isPending} type="submit">
        {isPending ? "登录中…" : "登录"}
      </Button>
    </form>
  )
}
