"use client"

import { useActionState, useEffect, useRef } from "react"
import { toast } from "sonner"

import type { CompanyActionState } from "@/app/actions/companies"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
  const wasPending = useRef(false)

  useEffect(() => {
    if (wasPending.current && !isPending && state.formError === null) {
      toast.success("企业已归档")
    }
    wasPending.current = isPending
  }, [isPending, state.formError])

  return (
    <div className="flex flex-col items-start gap-2">
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button type="button" variant="secondary" disabled={isPending}>
              归档企业
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
              <AlertDialogAction type="submit" variant="destructive" pending={isPending}>
                归档企业
              </AlertDialogAction>
            </form>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
