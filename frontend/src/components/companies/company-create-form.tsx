"use client"

import { useActionState } from "react"

import type { CompanyFormState } from "@/app/actions/companies"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"

type CompanyCreateFormProps = {
  readonly action: (state: CompanyFormState, formData: FormData) => Promise<CompanyFormState>
}

export function CompanyCreateForm({ action }: CompanyCreateFormProps) {
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

      <FormField error={state.fieldErrors.name} id="name" label="企业名称" type="text" />

      <Field data-invalid={state.fieldErrors.profile_text ? true : undefined}>
        <FieldLabel htmlFor="profile_text">企业简介</FieldLabel>
        <Textarea
          aria-invalid={state.fieldErrors.profile_text ? true : undefined}
          defaultValue=""
          id="profile_text"
          name="profile_text"
          rows={5}
        />
        {state.fieldErrors.profile_text ? (
          <FieldError>{state.fieldErrors.profile_text}</FieldError>
        ) : null}
      </Field>

      <div>
        <Button type="submit" disabled={isPending}>
          {isPending ? "创建中…" : "创建企业"}
        </Button>
      </div>
    </form>
  )
}
