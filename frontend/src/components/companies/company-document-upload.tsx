"use client"

import { useActionState } from "react"

import type { CompanyActionState } from "@/app/actions/companies"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type CompanyDocumentUploadProps = {
  readonly action: (state: CompanyActionState, formData: FormData) => Promise<CompanyActionState>
  readonly companyId: string
}

export function CompanyDocumentUpload({ action, companyId }: CompanyDocumentUploadProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <form action={formAction} className="flex flex-col gap-4" encType="multipart/form-data">
      <input name="company_id" type="hidden" value={companyId} />
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
      <Field>
        <FieldLabel htmlFor="file">上传资料（PDF / DOCX / TXT，最大 10 MB）</FieldLabel>
        <Input
          accept=".pdf,.docx,.txt,text/plain,application/pdf"
          id="file"
          name="file"
          type="file"
        />
      </Field>
      <div>
        <Button pending={isPending} type="submit">
          上传文档
        </Button>
      </div>
    </form>
  )
}
