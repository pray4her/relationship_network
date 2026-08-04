"use client"

import { useActionState } from "react"

import type { CompanyActionState } from "@/app/actions/companies"
import { Button } from "@/components/ui/button"

type CompanyArchiveButtonProps = {
  readonly action: (state: CompanyActionState, formData: FormData) => Promise<CompanyActionState>
  readonly companyId: string
}

export function CompanyArchiveButton({ action, companyId }: CompanyArchiveButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <form action={formAction} className="table-actions">
      <input name="company_id" type="hidden" value={companyId} />
      {state.formError ? (
        <p className="form-error" role="alert">
          {state.formError}
        </p>
      ) : null}
      <Button type="submit" mode="secondary" disabled={isPending}>
        {isPending ? "归档中…" : "归档企业"}
      </Button>
    </form>
  )
}
