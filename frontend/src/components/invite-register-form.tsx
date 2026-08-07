"use client"

import { useActionState } from "react"

import type { AuthFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type InviteRegisterFormProps = {
  readonly action: (state: AuthFormState, formData: FormData) => Promise<AuthFormState>
  readonly email: string
  readonly inviteToken: string
  readonly tenantName: string
}

export function InviteRegisterForm({
  action,
  email,
  inviteToken,
  tenantName,
}: InviteRegisterFormProps) {
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

      <input name="invite_token" type="hidden" value={inviteToken} />
      <p className="text-sm text-muted-foreground">注册后将直接加入租户：{tenantName}</p>

      <Field>
        <FieldLabel htmlFor="email">邮箱</FieldLabel>
        <Input id="email" name="email" readOnly type="email" value={email} />
        <FieldDescription>邮箱已锁定为邀请邮箱</FieldDescription>
      </Field>
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

      <Button className="w-full" disabled={isPending} type="submit">
        {isPending ? "提交中…" : "注册并接受邀请"}
      </Button>
    </form>
  )
}
