"use client"

import { useActionState } from "react"

import type { CompanyFormState } from "@/app/actions/companies"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

type CompanyEditFormProps = {
  readonly action: (state: CompanyFormState, formData: FormData) => Promise<CompanyFormState>
  readonly companyId: string
  readonly name: string
  readonly profileText: string
}

export function CompanyEditForm({ action, companyId, name, profileText }: CompanyEditFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      <input name="company_id" type="hidden" value={companyId} />
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}

      <Field data-invalid={state.fieldErrors.name ? true : undefined}>
        <FieldLabel htmlFor="name">企业名称</FieldLabel>
        <Input
          aria-invalid={state.fieldErrors.name ? true : undefined}
          defaultValue={name}
          id="name"
          name="name"
          type="text"
        />
        {state.fieldErrors.name ? <FieldError>{state.fieldErrors.name}</FieldError> : null}
      </Field>

      <Field data-invalid={state.fieldErrors.profile_text ? true : undefined}>
        <FieldLabel htmlFor="profile_text">企业简介</FieldLabel>
        <Textarea
          aria-invalid={state.fieldErrors.profile_text ? true : undefined}
          defaultValue={profileText}
          id="profile_text"
          name="profile_text"
          rows={6}
        />
        {state.fieldErrors.profile_text ? (
          <FieldError>{state.fieldErrors.profile_text}</FieldError>
        ) : null}
      </Field>

      <div>
        <Button type="submit" disabled={isPending}>
          {isPending ? "保存中…" : "保存更改"}
        </Button>
      </div>
    </form>
  )
}
