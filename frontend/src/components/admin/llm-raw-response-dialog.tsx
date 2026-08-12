"use client"

import { useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  type LlmRawResponse,
  llmCallErrorSchema,
  llmRawResponseSchema,
} from "@/lib/llm-call-contract"
import { formatDiagnosticDateTime } from "@/lib/llm-call-view"

type ViewState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading" }
  | { readonly kind: "success"; readonly response: LlmRawResponse }
  | { readonly kind: "expired" }
  | { readonly kind: "keyUnavailable" }
  | { readonly kind: "forbidden" }
  | { readonly kind: "networkError" }

function formatBody(response: LlmRawResponse): string {
  if (response.body === "") return "（响应正文为空）"
  if (response.encoding !== "utf-8") return response.body
  try {
    return JSON.stringify(JSON.parse(response.body) as unknown, null, 2)
  } catch {
    return response.body
  }
}

function ResponseState({ state }: { readonly state: ViewState }) {
  switch (state.kind) {
    case "idle":
    case "loading":
      return <p>{state.kind === "loading" ? "正在解密并读取原始响应…" : "尚未请求原始响应。"}</p>
    case "expired":
      return (
        <Alert>
          <AlertDescription>原始响应不存在或已超过 90 天保留期。</AlertDescription>
        </Alert>
      )
    case "keyUnavailable":
      return (
        <Alert>
          <AlertDescription>历史密钥不可用，无法解密这条原始响应。</AlertDescription>
        </Alert>
      )
    case "forbidden":
      return (
        <Alert variant="destructive">
          <AlertDescription>会话已过期或当前账号无权查看原始响应。</AlertDescription>
        </Alert>
      )
    case "networkError":
      return (
        <Alert variant="destructive">
          <AlertDescription>原始响应服务暂时不可用，请稍后重试。</AlertDescription>
        </Alert>
      )
    case "success":
      return (
        <div className="grid min-w-0 gap-4">
          <dl className="grid grid-cols-2 gap-3 text-sm max-sm:grid-cols-1">
            <div>
              <dt className="text-muted-foreground">HTTP 状态</dt>
              <dd className="m-0 font-mono tabular-nums">{state.response.http_status ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">内容类型</dt>
              <dd className="m-0 break-all font-mono">{state.response.content_type ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">响应序号</dt>
              <dd className="m-0 font-mono tabular-nums">{state.response.response_sequence}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">到期时间</dt>
              <dd className="m-0 tabular-nums">
                {formatDiagnosticDateTime(state.response.expires_at)}
              </dd>
            </div>
          </dl>
          <pre className="m-0 max-h-[55vh] overflow-auto rounded-md border border-border bg-muted p-4 whitespace-pre-wrap break-words font-mono text-sm leading-relaxed">
            {formatBody(state.response)}
          </pre>
        </div>
      )
  }
}

export function LlmRawResponseDialog({
  available,
  callId,
}: {
  readonly available: boolean
  readonly callId: string
}) {
  const [open, setOpen] = useState(false)
  const [state, setState] = useState<ViewState>({ kind: "idle" })

  async function reveal(): Promise<void> {
    setOpen(true)
    setState({ kind: "loading" })
    try {
      const response = await fetch(
        `/api/admin/llm-calls/${encodeURIComponent(callId)}/raw-response`,
        { cache: "no-store", method: "POST" },
      )
      const body: unknown = await response.json().catch(() => null)
      if (response.ok) {
        const parsed = llmRawResponseSchema.safeParse(body)
        setState(
          parsed.success ? { kind: "success", response: parsed.data } : { kind: "networkError" },
        )
        return
      }
      const error = llmCallErrorSchema.safeParse(body)
      if (response.status === 404) setState({ kind: "expired" })
      else if (
        response.status === 409 &&
        error.success &&
        error.data.detail === "llm_raw_response_key_unavailable"
      ) {
        setState({ kind: "keyUnavailable" })
      } else if (response.status === 401 || response.status === 403) {
        setState({ kind: "forbidden" })
      } else setState({ kind: "networkError" })
    } catch {
      setState({ kind: "networkError" })
    }
  }

  return (
    <>
      <Button disabled={!available} onClick={() => void reveal()} type="button">
        {available ? "查看原始响应" : "原始响应不可用"}
      </Button>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>原始供应商响应</DialogTitle>
            <DialogDescription>
              此操作已写入平台审计日志。页面不会缓存解密后的响应。
            </DialogDescription>
          </DialogHeader>
          <div aria-live="polite" className="min-w-0">
            <ResponseState state={state} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
