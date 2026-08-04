"use client"

import { useActionState } from "react"

import type { CompanyFormState } from "@/app/actions/companies"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type CompanyEditFormProps = {
  readonly action: (state: CompanyFormState, formData: FormData) => Promise<CompanyFormState>
  readonly companyId: string
  readonly name: string
  readonly profileText: string
}

export function CompanyEditForm({
  action,
  companyId,
  name,
  profileText,
}: CompanyEditFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })

  return (
    <form action={formAction} className="auth-form" noValidate>
      <input name="company_id" type="hidden" value={companyId} />
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}

      <div className="form-field">
        <Label htmlFor="name">企业名称</Label>
        <Input
          defaultValue={name}
          id="name"
          invalid={Boolean(state.fieldErrors.name)}
          name="name"
          type="text"
        />
        {state.fieldErrors.name ? (
          <p className="field-error" role="alert">
            {state.fieldErrors.name}
          </p>
        ) : null}
      </div>

      <div className="form-field">
        <Label htmlFor="profile_text">企业简介</Label>
        <textarea
          className="field-input"
          defaultValue={profileText}
          id="profile_text"
          name="profile_text"
          rows={6}
        />
        {state.fieldErrors.profile_text ? (
          <p className="field-error" role="alert">
            {state.fieldErrors.profile_text}
          </p>
        ) : null}
      </div>

      <Button type="submit" disabled={isPending}>
        {isPending ? "保存中…" : "保存更改"}
      </Button>
    </form>
  )
}
