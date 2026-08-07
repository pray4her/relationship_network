"use client"

import { useActionState } from "react"

import type { CompanyActionState } from "@/app/actions/companies"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

type CompanyArchiveButtonProps = {
  readonly action: (state: CompanyActionState, formData: FormData) => Promise<CompanyActionState>
  readonly companyId: string
}

export function CompanyArchiveButton({ action, companyId }: CompanyArchiveButtonProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button type="button" variant="secondary" disabled={isPending}>
              {isPending ? "归档中…" : "归档企业"}
            </Button>
          }
        />
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>归档企业</AlertDialogTitle>
            <AlertDialogDescription>
              归档后该企业将变为只读，不能再编辑或上传文档。确定要归档企业吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <form action={formAction}>
              <input name="company_id" type="hidden" value={companyId} />
              <AlertDialogAction type="submit" variant="destructive" disabled={isPending}>
                {isPending ? "归档中…" : "归档企业"}
              </AlertDialogAction>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.formError ? (
        <p className="text-sm text-destructive" role="alert">
          {state.formError}
        </p>
      ) : null}
    </div>
  )
}
