"use client"

import { useActionState } from "react"

import type { CompanyFormState } from "@/app/actions/companies"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"

type CompanyCreateFormProps = {
  readonly action: (state: CompanyFormState, formData: FormData) => Promise<CompanyFormState>
}

export function CompanyCreateForm({ action }: CompanyCreateFormProps) {
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

      <FormField error={state.fieldErrors.name} id="name" label="企业名称" type="text" />

      <div className="form-field">
        <Label htmlFor="profile_text">企业简介</Label>
        <textarea
          className="field-input"
          defaultValue=""
          id="profile_text"
          name="profile_text"
          rows={5}
        />
        {state.fieldErrors.profile_text ? (
          <p className="field-error" role="alert">
            {state.fieldErrors.profile_text}
          </p>
        ) : null}
      </div>

      <Button type="submit" disabled={isPending}>
        {isPending ? "创建中…" : "创建企业"}
      </Button>
    </form>
  )
}
