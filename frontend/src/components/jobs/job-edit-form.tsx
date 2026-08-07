"use client"

import { useActionState } from "react"

import type { JobFormState } from "@/app/actions/jobs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

type JobEditFormProps = {
  readonly action: (state: JobFormState, formData: FormData) => Promise<JobFormState>
  readonly jobId: string
  readonly title: string
  readonly description: string
}

export function JobEditForm({ action, jobId, title, description }: JobEditFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      <input name="job_id" type="hidden" value={jobId} />
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}

      <Field data-invalid={state.fieldErrors.title ? true : undefined}>
        <FieldLabel htmlFor="title">职位名称</FieldLabel>
        <Input
          aria-invalid={state.fieldErrors.title ? true : undefined}
          defaultValue={title}
          id="title"
          name="title"
          type="text"
        />
        {state.fieldErrors.title ? <FieldError>{state.fieldErrors.title}</FieldError> : null}
      </Field>

      <Field data-invalid={state.fieldErrors.description ? true : undefined}>
        <FieldLabel htmlFor="description">职位描述</FieldLabel>
        <Textarea
          aria-invalid={state.fieldErrors.description ? true : undefined}
          defaultValue={description}
          id="description"
          name="description"
          rows={6}
        />
        {state.fieldErrors.description ? (
          <FieldError>{state.fieldErrors.description}</FieldError>
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
