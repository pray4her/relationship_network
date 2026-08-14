"use client"

import { useActionState, useState } from "react"

import type { JobFormState } from "@/app/actions/jobs"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"

export type JobCompanyOption = {
  readonly id: string
  readonly name: string
}

type JobCreateFormProps = {
  readonly action: (state: JobFormState, formData: FormData) => Promise<JobFormState>
  readonly companies: readonly JobCompanyOption[]
}

export function JobCreateForm({ action, companies }: JobCreateFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    fieldErrors: {},
    formError: null,
  })
  const [companyId, setCompanyId] = useState("")

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}

      <Field data-invalid={state.fieldErrors.company_id ? true : undefined}>
        <FieldLabel id="job-create-company-label">所属企业</FieldLabel>
        <input name="company_id" type="hidden" value={companyId} />
        <Select
          onValueChange={(value) => setCompanyId(typeof value === "string" ? value : "")}
          value={companyId || undefined}
        >
          <SelectTrigger aria-labelledby="job-create-company-label" className="w-full">
            <SelectValue placeholder="请选择企业" />
          </SelectTrigger>
          <SelectContent>
            {companies.map((company) => (
              <SelectItem key={company.id} value={company.id}>
                {company.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {state.fieldErrors.company_id ? (
          <FieldError>{state.fieldErrors.company_id}</FieldError>
        ) : null}
      </Field>

      <FormField error={state.fieldErrors.title} id="title" label="职位名称" type="text" />

      <Field data-invalid={state.fieldErrors.description ? true : undefined}>
        <FieldLabel htmlFor="description">职位描述</FieldLabel>
        <Textarea
          aria-invalid={state.fieldErrors.description ? true : undefined}
          defaultValue=""
          id="description"
          name="description"
          rows={5}
        />
        {state.fieldErrors.description ? (
          <FieldError>{state.fieldErrors.description}</FieldError>
        ) : null}
      </Field>

      <div>
        <Button pending={isPending} type="submit">
          {isPending ? "创建中…" : "创建职位"}
        </Button>
      </div>
    </form>
  )
}
