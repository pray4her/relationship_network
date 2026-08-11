"use client"

import { RotateCcwIcon, ShieldCheckIcon, XIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { createContext, useContext, useEffect, useState, useTransition } from "react"

import {
  cancelLlmConfigurationAction,
  copyLlmConfigurationAction,
  submitLlmConfigurationAction,
} from "@/app/actions/llm-configuration"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogBody,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  type LlmAttempt,
  type LlmAttemptStatus,
  type LlmWorkspace,
  llmAttemptEventDataSchema,
} from "@/lib/llm-configuration-contract"

const terminalStatuses = new Set<LlmAttemptStatus>([
  "cancelled",
  "conflicted",
  "failed",
  "succeeded",
])

const statusLabels: Record<LlmAttemptStatus, string> = {
  cancel_requested: "正在取消",
  cancelled: "已取消",
  conflicted: "配置冲突",
  failed: "探测失败",
  queued: "等待执行",
  retry_scheduled: "等待重试",
  running: "正在探测",
  succeeded: "已启用",
}

const errorLabels: Record<string, string> = {
  authentication_failed: "OpenRouter 凭据无效，请检查服务端环境变量。",
  incompatible_llm_assets: "提示词与职位需求 Schema 不兼容。",
  insufficient_balance: "OpenRouter 余额不足，请充值后重新提交。",
  invalid_structured_output: "模型未返回所需的严格结构化结果。",
  model_unavailable: "该模型当前不可用或无法满足参数要求。",
  openrouter_not_configured: "服务端尚未配置 OpenRouter API Key。",
  privacy_routing_rejected: "没有满足零数据保留要求的供应商路由。",
  stale_current_configuration: "探测期间当前配置已变化，本次没有启用。",
  unsupported_parameters: "模型不支持严格结构化输出所需参数。",
}

type FieldErrors = Readonly<Record<string, string>>

type WorkbenchContextValue = {
  readonly activeAttempt: LlmAttempt | null
  readonly busy: boolean
  readonly fieldErrors: FieldErrors
  readonly formError: string | null
  readonly pending: boolean
  readonly setActiveAttempt: (attempt: LlmAttempt) => void
  readonly setActionError: (message: string | null) => void
  readonly setFieldErrors: (errors: FieldErrors) => void
  readonly startAction: (action: () => Promise<void>) => void
  readonly workspace: LlmWorkspace
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null)

function useWorkbench(): WorkbenchContextValue {
  const context = useContext(WorkbenchContext)
  if (context === null) throw new Error("LLM workbench component must be inside its provider")
  return context
}

function WorkbenchProvider({
  children,
  workspace,
}: {
  readonly children: React.ReactNode
  readonly workspace: LlmWorkspace
}) {
  const router = useRouter()
  const [activeAttempt, setActiveAttempt] = useState(workspace.active_attempt)
  const [formError, setActionError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [pending, startTransition] = useTransition()
  const busy = activeAttempt !== null && !terminalStatuses.has(activeAttempt.status)
  const activeAttemptId = activeAttempt?.id ?? null
  const activeAttemptStatus = activeAttempt?.status ?? null

  useEffect(() => {
    if (workspace.active_attempt !== null) setActiveAttempt(workspace.active_attempt)
  }, [workspace.active_attempt])

  useEffect(() => {
    if (
      activeAttemptId === null ||
      activeAttemptStatus === null ||
      terminalStatuses.has(activeAttemptStatus)
    ) {
      return
    }
    const source = new EventSource(
      `/api/admin/llm-configuration-attempts/${activeAttemptId}/events`,
    )
    const eventNames: LlmAttemptStatus[] = [
      "queued",
      "running",
      "retry_scheduled",
      "cancel_requested",
      "succeeded",
      "failed",
      "conflicted",
      "cancelled",
    ]
    const onEvent = (event: Event) => {
      if (!(event instanceof MessageEvent) || typeof event.data !== "string") return
      const raw: unknown = JSON.parse(event.data)
      const parsed = llmAttemptEventDataSchema.safeParse(raw)
      if (!parsed.success) return
      setActiveAttempt((attempt) =>
        attempt === null
          ? null
          : {
              ...attempt,
              error_code:
                typeof parsed.data.payload["error_code"] === "string"
                  ? parsed.data.payload["error_code"]
                  : attempt.error_code,
              next_attempt_at:
                typeof parsed.data.payload["next_attempt_at"] === "string"
                  ? parsed.data.payload["next_attempt_at"]
                  : attempt.next_attempt_at,
              status: parsed.data.status,
              updated_at: parsed.data.created_at,
            },
      )
      if (terminalStatuses.has(parsed.data.status)) {
        source.close()
        router.refresh()
      }
    }
    for (const name of eventNames) source.addEventListener(name, onEvent)
    return () => source.close()
  }, [activeAttemptId, activeAttemptStatus, router])

  const startAction = (action: () => Promise<void>) => {
    startTransition(() => {
      void action()
    })
  }

  return (
    <WorkbenchContext.Provider
      value={{
        activeAttempt,
        busy,
        fieldErrors,
        formError,
        pending,
        setActionError,
        setActiveAttempt,
        setFieldErrors,
        startAction,
        workspace,
      }}
    >
      {children}
    </WorkbenchContext.Provider>
  )
}

function ConfigurationFacts({ workspace }: { readonly workspace: LlmWorkspace }) {
  const current = workspace.current
  return (
    <dl className="grid grid-cols-2 gap-x-[var(--space-8)] gap-y-[var(--space-4)] max-sm:grid-cols-1">
      <div>
        <dt className="text-caption text-muted-foreground">模型</dt>
        <dd className="m-0 font-medium">{current.model}</dd>
      </div>
      <div>
        <dt className="text-caption text-muted-foreground">提示词版本</dt>
        <dd className="m-0 font-mono text-sm">{current.prompt_version_id}</dd>
      </div>
      <div>
        <dt className="text-caption text-muted-foreground">Temperature</dt>
        <dd className="m-0 tabular-nums">{current.temperature}</dd>
      </div>
      <div>
        <dt className="text-caption text-muted-foreground">输出 / 超时</dt>
        <dd className="m-0 tabular-nums">
          {current.max_output_tokens} tokens · {current.request_timeout_seconds} 秒
        </dd>
      </div>
    </dl>
  )
}

function CurrentConfiguration() {
  const { workspace } = useWorkbench()
  return (
    <Card variant="elevated">
      <CardHeader>
        <ShieldCheckIcon aria-hidden="true" className="size-[var(--icon-size-md)] text-primary" />
        <div>
          <CardTitle>当前启用配置</CardTitle>
          <CardDescription>
            版本 {workspace.current.version_number} · 已通过固定最小探测
          </CardDescription>
        </div>
        <CardAction>
          <Badge variant="secondary">运行中</Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <ConfigurationFacts workspace={workspace} />
      </CardContent>
    </Card>
  )
}

function CandidateForm() {
  const {
    busy,
    fieldErrors,
    pending,
    setActionError,
    setActiveAttempt,
    setFieldErrors,
    startAction,
    workspace,
  } = useWorkbench()
  const current = workspace.current

  const submit = (formData: FormData) => {
    setActionError(null)
    setFieldErrors({})
    startAction(async () => {
      const result = await submitLlmConfigurationAction(formData)
      if (result.kind === "ok") {
        setActiveAttempt(result.attempt)
        return
      }
      setActionError(result.formError)
      setFieldErrors(result.fieldErrors)
    })
  }

  return (
    <Card variant="outlined">
      <CardHeader>
        <div>
          <CardTitle>候选配置</CardTitle>
          <CardDescription>提交后异步探测；成功时创建并启用新的不可变版本。</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <form action={submit} className="space-y-[var(--space-5)]">
          <input name="expected_current_version_id" type="hidden" value={current.id} />
          <FieldGroup>
            <Field data-invalid={fieldErrors["model"] ? true : undefined}>
              <FieldLabel htmlFor="llm-model">OpenRouter 模型</FieldLabel>
              <Input
                aria-invalid={fieldErrors["model"] ? true : undefined}
                autoComplete="off"
                defaultValue={current.model}
                disabled={busy || pending}
                id="llm-model"
                maxLength={200}
                name="model"
                required
              />
              <FieldDescription>只发送这个模型 ID；同模型内仍可选择合规供应商。</FieldDescription>
              <FieldError>{fieldErrors["model"]}</FieldError>
            </Field>
            <Field data-invalid={fieldErrors["prompt_version_id"] ? true : undefined}>
              <FieldLabel htmlFor="prompt-version">提示词版本</FieldLabel>
              <select
                aria-invalid={fieldErrors["prompt_version_id"] ? true : undefined}
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
                defaultValue={current.prompt_version_id}
                disabled={busy || pending}
                id="prompt-version"
                name="prompt_version_id"
                required
              >
                {workspace.prompt_versions.map((prompt) => (
                  <option key={prompt.id} value={prompt.id}>
                    {prompt.id}
                  </option>
                ))}
              </select>
              <FieldError>{fieldErrors["prompt_version_id"]}</FieldError>
            </Field>
            <div className="grid grid-cols-3 gap-[var(--space-4)] max-md:grid-cols-1">
              <Field data-invalid={fieldErrors["temperature"] ? true : undefined}>
                <FieldLabel htmlFor="temperature">Temperature</FieldLabel>
                <Input
                  aria-invalid={fieldErrors["temperature"] ? true : undefined}
                  defaultValue={current.temperature}
                  disabled={busy || pending}
                  id="temperature"
                  max={1}
                  min={0}
                  name="temperature"
                  required
                  step={0.1}
                  type="number"
                />
                <FieldError>{fieldErrors["temperature"]}</FieldError>
              </Field>
              <Field data-invalid={fieldErrors["max_output_tokens"] ? true : undefined}>
                <FieldLabel htmlFor="max-output-tokens">最大输出 tokens</FieldLabel>
                <Input
                  aria-invalid={fieldErrors["max_output_tokens"] ? true : undefined}
                  defaultValue={current.max_output_tokens}
                  disabled={busy || pending}
                  id="max-output-tokens"
                  max={16384}
                  min={1024}
                  name="max_output_tokens"
                  required
                  step={1}
                  type="number"
                />
                <FieldError>{fieldErrors["max_output_tokens"]}</FieldError>
              </Field>
              <Field data-invalid={fieldErrors["request_timeout_seconds"] ? true : undefined}>
                <FieldLabel htmlFor="request-timeout">请求超时（秒）</FieldLabel>
                <Input
                  aria-invalid={fieldErrors["request_timeout_seconds"] ? true : undefined}
                  defaultValue={current.request_timeout_seconds}
                  disabled={busy || pending}
                  id="request-timeout"
                  max={300}
                  min={30}
                  name="request_timeout_seconds"
                  required
                  step={1}
                  type="number"
                />
                <FieldError>{fieldErrors["request_timeout_seconds"]}</FieldError>
              </Field>
            </div>
          </FieldGroup>
          <Button disabled={busy || pending} type="submit">
            {pending && <Spinner aria-hidden="true" size="sm" variant="inverse" />}
            {busy ? "已有变更正在执行" : "提交并探测"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function AttemptProgress() {
  const { activeAttempt, formError, pending, setActionError, setActiveAttempt, startAction } =
    useWorkbench()
  const [dialogOpen, setDialogOpen] = useState(false)
  if (activeAttempt === null) {
    return (
      <Card variant="outlined">
        <CardHeader>
          <CardTitle>变更进度</CardTitle>
        </CardHeader>
        <CardContent className="space-y-[var(--space-4)] text-sm text-muted-foreground">
          <p className="m-0">当前没有待处理的配置变更。</p>
          {formError && (
            <Alert>
              <AlertTitle>操作未完成</AlertTitle>
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    )
  }
  const terminal = terminalStatuses.has(activeAttempt.status)
  const error = activeAttempt.error_code
    ? (errorLabels[activeAttempt.error_code] ?? activeAttempt.error_code)
    : null

  const cancel = () => {
    setDialogOpen(false)
    setActionError(null)
    startAction(async () => {
      const result = await cancelLlmConfigurationAction(activeAttempt.id)
      if (result.kind === "ok") setActiveAttempt(result.attempt)
      else setActionError(result.formError)
    })
  }

  return (
    <Card aria-live="polite" variant="outlined">
      <CardHeader>
        {!terminal && <Spinner aria-hidden="true" size="sm" />}
        <div>
          <CardTitle>变更进度</CardTitle>
          <CardDescription>尝试 {activeAttempt.id.slice(0, 8)}</CardDescription>
        </div>
        <CardAction>
          <Badge variant="secondary">{statusLabels[activeAttempt.status]}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-[var(--space-4)]">
        <p className="m-0 text-sm text-muted-foreground">
          已发起 {activeAttempt.external_call_count} / 3 次外部请求
          {activeAttempt.next_attempt_at
            ? `；计划于 ${new Date(activeAttempt.next_attempt_at).toLocaleString("zh-CN")} 重试`
            : ""}
        </p>
        {error && (
          <Alert>
            <AlertTitle>需要处理</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {formError && (
          <Alert>
            <AlertTitle>操作未完成</AlertTitle>
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        )}
        {!terminal && activeAttempt.status !== "cancel_requested" && (
          <AlertDialog onOpenChange={setDialogOpen} open={dialogOpen}>
            <AlertDialogTrigger render={<Button size="sm" variant="outline" />}>
              <XIcon aria-hidden="true" />
              取消变更
            </AlertDialogTrigger>
            <AlertDialogContent size="sm" variant="destructive">
              <AlertDialogHeader>
                <AlertDialogTitle>取消这次配置变更？</AlertDialogTitle>
                <AlertDialogDescription>
                  已完成的探测事实会保留，但不会启用候选配置。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogBody>
                取消请求会在安全点生效，正在进行的网络请求可能先完成。
              </AlertDialogBody>
              <AlertDialogFooter>
                <AlertDialogCancel>继续等待</AlertDialogCancel>
                <AlertDialogAction disabled={pending} onClick={cancel} variant="destructive">
                  确认取消
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </CardContent>
    </Card>
  )
}

function RestoreButton({ versionId }: { readonly versionId: string }) {
  const { busy, pending, setActionError, setActiveAttempt, startAction, workspace } = useWorkbench()
  const [open, setOpen] = useState(false)
  const restore = () => {
    setOpen(false)
    setActionError(null)
    startAction(async () => {
      const result = await copyLlmConfigurationAction(versionId, workspace.current.id)
      if (result.kind === "ok") setActiveAttempt(result.attempt)
      else setActionError(result.formError)
    })
  }
  return (
    <AlertDialog onOpenChange={setOpen} open={open}>
      <AlertDialogTrigger render={<Button disabled={busy || pending} size="sm" variant="ghost" />}>
        <RotateCcwIcon aria-hidden="true" />
        复制并探测
      </AlertDialogTrigger>
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogTitle>从历史版本创建新配置？</AlertDialogTitle>
          <AlertDialogDescription>
            系统会复制参数并重新探测，不会重新启用旧记录。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogBody>只有探测成功且当前版本未变化时，才会创建并启用新版本。</AlertDialogBody>
        <AlertDialogFooter>
          <AlertDialogCancel>返回</AlertDialogCancel>
          <AlertDialogAction disabled={pending} onClick={restore}>
            复制并探测
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function ConfigurationHistory() {
  const { workspace } = useWorkbench()
  return (
    <Card variant="outlined">
      <CardHeader>
        <div>
          <CardTitle>配置版本历史</CardTitle>
          <CardDescription>版本不可原地修改；恢复会生成新的版本。</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {workspace.history.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无历史版本。</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>提示词</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>
                  <span className="sr-only">操作</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workspace.history.map((version) => (
                <TableRow key={version.id}>
                  <TableCell className="font-medium">
                    v{version.version_number}
                    {version.id === workspace.current.id && (
                      <Badge className="ml-2" variant="secondary">
                        当前
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{version.model}</TableCell>
                  <TableCell className="font-mono text-xs">{version.prompt_version_id}</TableCell>
                  <TableCell className="tabular-nums">
                    {new Date(version.created_at).toLocaleString("zh-CN")}
                  </TableCell>
                  <TableCell className="text-right">
                    <RestoreButton versionId={version.id} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

export function LlmConfigurationWorkbench({ workspace }: { readonly workspace: LlmWorkspace }) {
  return (
    <WorkbenchProvider workspace={workspace}>
      <CurrentConfiguration />
      <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.75fr)] gap-[var(--space-6)] max-lg:grid-cols-1">
        <CandidateForm />
        <AttemptProgress />
      </div>
      <ConfigurationHistory />
    </WorkbenchProvider>
  )
}
