"use client"

import { useActionState } from "react"

import type { AuthFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
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
    <form action={formAction} className="auth-form" noValidate>
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
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

      <Button type="submit" disabled={isPending}>
        {isPending ? "登录中…" : "登录"}
      </Button>
    </form>
  )
}
