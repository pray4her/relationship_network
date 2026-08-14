"use client"

import { useActionState } from "react"

import type { AuthFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

type RegisterFormProps = {
  readonly action: (state: AuthFormState, formData: FormData) => Promise<AuthFormState>
}

export function RegisterForm({ action }: RegisterFormProps) {
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
        autoComplete="new-password"
        error={state.fieldErrors.password}
        hint="至少 8 位字符"
        id="password"
        label="密码"
        type="password"
      />
      <FormField
        autoComplete="name"
        error={state.fieldErrors.display_name}
        id="display_name"
        label="显示名称"
        type="text"
      />
      <FormField
        error={state.fieldErrors.tenant_name}
        hint="选填，留空则自动生成"
        id="tenant_name"
        label="租户名称"
        type="text"
      />

      <Button className="w-full" pending={isPending} type="submit">
        创建账户
      </Button>
    </form>
  )
}
