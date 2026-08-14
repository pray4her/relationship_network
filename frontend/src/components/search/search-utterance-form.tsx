"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { submitSearchAction } from "@/app/actions/search"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID()
  return `search-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function SearchUtteranceForm() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(formData: FormData) {
    formData.set("idempotency_key", newIdempotencyKey())
    setError(null)
    startTransition(async () => {
      const result = await submitSearchAction(formData)
      if (result.kind === "ok") {
        router.push(`/search/${result.runId}`)
      } else {
        setError(result.message)
      }
    })
  }

  return (
    <form action={handleSubmit} className="flex flex-col gap-3">
      <Textarea
        name="utterance"
        aria-label="搜索原句"
        maxLength={4000}
        placeholder="用自然语言描述你正在寻找的人才，例如：寻找现任机构为北美高校、h 指数超过 30、从事人工智能研究的华人学者"
        rows={4}
        required
      />
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          最多 4000 个字符，提交后立即执行搜索并计 1 次额度。
        </p>
        <Button type="submit" pending={pending}>
          {pending ? "搜索中…" : "搜索人才"}
        </Button>
      </div>
    </form>
  )
}
