"use client"

import { useActionState } from "react"

import type { JobActionState } from "@/app/actions/jobs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type JobMaterialUploadProps = {
  readonly action: (state: JobActionState, formData: FormData) => Promise<JobActionState>
  readonly jobId: string
}

export function JobMaterialUpload({ action, jobId }: JobMaterialUploadProps) {
  const [state, formAction, isPending] = useActionState(action, { formError: null })

  return (
    <form action={formAction} className="flex flex-col gap-4" encType="multipart/form-data">
      <input name="job_id" type="hidden" value={jobId} />
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
      <Field>
        <FieldLabel htmlFor="file">上传材料（PDF / DOCX / TXT，最大 10 MB）</FieldLabel>
        <Input
          accept=".pdf,.docx,.txt,text/plain,application/pdf"
          id="file"
          name="file"
          type="file"
        />
      </Field>
      <div>
        <Button type="submit" disabled={isPending}>
          {isPending ? "上传中…" : "上传材料"}
        </Button>
      </div>
    </form>
  )
}
