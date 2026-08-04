"use client"

import { useActionState } from "react"

import type { CompanyActionState } from "@/app/actions/companies"
import { Button } from "@/components/ui/button"

type CompanyDocumentUploadProps = {
  readonly action: (state: CompanyActionState, formData: FormData) => Promise<CompanyActionState>
  readonly companyId: string
}

export function CompanyDocumentUpload({ action, companyId }: CompanyDocumentUploadProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <form action={formAction} className="auth-form" encType="multipart/form-data">
      <input name="company_id" type="hidden" value={companyId} />
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}
      <label className="field" htmlFor="file">
        <span className="field-label">上传资料（PDF / DOCX / TXT，最大 10 MB）</span>
        <input accept=".pdf,.docx,.txt,text/plain,application/pdf" id="file" name="file" type="file" />
      </label>
      <Button type="submit" disabled={isPending}>
        {isPending ? "上传中…" : "上传文档"}
      </Button>
    </form>
  )
}
