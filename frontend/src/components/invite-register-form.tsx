"use client"

import { useActionState } from "react"

import type { AuthFormState } from "@/app/actions/auth"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

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
    <form action={formAction} className="auth-form" noValidate>
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}

      <input name="invite_token" type="hidden" value={inviteToken} />
      <p className="field-hint">注册后将直接加入租户：{tenantName}</p>

      <div className="form-field">
        <Label htmlFor="email">邮箱</Label>
        <Input id="email" name="email" readOnly type="email" value={email} />
        <p className="field-hint">邮箱已锁定为邀请邮箱</p>
      </div>
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

      <Button type="submit" disabled={isPending}>
        {isPending ? "提交中…" : "注册并接受邀请"}
      </Button>
    </form>
  )
}
