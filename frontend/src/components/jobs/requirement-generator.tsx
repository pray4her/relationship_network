"use client"

import { RefreshCwIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { createContext, use, useEffect, useMemo, useRef, useState, useTransition } from "react"

import {
  cancelRequirementTaskAction,
  generateRequirementDraftAction,
} from "@/app/actions/job-requirements"
import { JobRequirementDraftEditor } from "@/components/jobs/requirement-draft-editor"
import { DataRegion, DataRegionContent, DataRegionFooter } from "@/components/layout/page"
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
import { Checkbox } from "@/components/ui/checkbox"
import {
  Field,
  FieldContent,
  FieldCount,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldHeader,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type {
  RequirementDraft,
  RequirementSource,
  RequirementTask,
  RequirementTaskStatus,
  RequirementWorkspace,
} from "@/lib/job-requirement-contract"
import { requirementTaskEventSchema } from "@/lib/job-requirement-contract"

type SourceEditorState = {
  readonly selected: boolean
  readonly correctedText: string
}

type RequirementGeneratorState = {
  readonly sourceState: Readonly<Record<string, SourceEditorState>>
  readonly task: RequirementTask | null
  readonly actionError: string | null
  readonly pending: boolean
  readonly connection: "closed" | "connecting" | "open" | "reconnecting"
}

type RequirementGeneratorActions = {
  readonly setCorrectedText: (sourceId: string, value: string) => void
  readonly setSelected: (sourceId: string, selected: boolean) => void
  readonly submit: () => void
  readonly refresh: () => void
  readonly cancel: () => void
}

type RequirementGeneratorMeta = {
  readonly editable: boolean
  readonly inputCharacterLimit: number
  readonly sources: readonly RequirementSource[]
  readonly totalCharacters: number
  readonly selectedCount: number
  readonly overLimit: boolean
  readonly summaryRef: React.RefObject<HTMLDivElement | null>
  readonly draft: RequirementDraft | null
  readonly configurationReady: boolean
  readonly canCancel: boolean
  readonly canManage: boolean
  readonly draftDirty: boolean
  readonly jobId: string
  readonly onDraftDirtyChange?: (dirty: boolean) => void
}

type RequirementGeneratorContextValue = {
  readonly state: RequirementGeneratorState
  readonly actions: RequirementGeneratorActions
  readonly meta: RequirementGeneratorMeta
}

const RequirementGeneratorContext = createContext<RequirementGeneratorContextValue | null>(null)
const terminalStatuses = new Set<RequirementTaskStatus>(["succeeded", "failed", "cancelled"])

const statusLabels: Record<RequirementTaskStatus, string> = {
  queued: "排队中",
  running: "生成中",
  retry_scheduled: "等待重试",
  cancel_requested: "正在取消",
  succeeded: "生成成功",
  failed: "生成失败",
  cancelled: "已取消",
}

const taskErrorMessages: Record<string, string> = {
  requirement_output_invalid: "模型结果未通过完整结构或来源证据校验。请检查来源后重新生成。",
  requirement_generation_unavailable: "生成服务暂时不可用。请稍后重新生成。",
  requirement_configuration_unavailable: "生成配置当前不可用。请联系平台管理员检查 v2 配置。",
  requirement_draft_exists: "该职位已有可编辑草稿，请先处理现有草稿。",
  requirement_draft_replacement_conflict: "当前草稿已发生变化，本次结果没有替换现有草稿。",
  job_archived: "职位已归档，迟到结果没有写入草稿。",
}

const taskTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: "Asia/Shanghai",
})

function useRequirementGenerator(): RequirementGeneratorContextValue {
  const context = use(RequirementGeneratorContext)
  if (context === null) {
    throw new Error("RequirementGenerator components must be inside RequirementGenerator.Provider")
  }
  return context
}

function normalizeForCount(value: string): string {
  return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").normalize("NFC")
}

function unicodeLength(value: string): number {
  return Array.from(normalizeForCount(value)).length
}

function submissionFingerprint(
  sources: readonly { readonly source_id: string; readonly corrected_text: string }[],
): string {
  return JSON.stringify(
    sources.map((source) => ({
      corrected_text: normalizeForCount(source.corrected_text),
      source_id: source.source_id,
    })),
  )
}

function initialSourceState(
  sources: readonly RequirementSource[],
): Record<string, SourceEditorState> {
  return Object.fromEntries(
    sources.map((source) => [
      source.source_id,
      { correctedText: source.original_text, selected: false },
    ]),
  )
}

function RequirementGeneratorProvider({
  archived,
  canManage,
  children,
  draftDirty = false,
  jobId,
  onDraftDirtyChange,
  workspace,
}: {
  readonly archived: boolean
  readonly canManage: boolean
  readonly children: React.ReactNode
  readonly draftDirty?: boolean
  readonly jobId: string
  readonly onDraftDirtyChange?: (dirty: boolean) => void
  readonly workspace: RequirementWorkspace
}) {
  const router = useRouter()
  const initialState = useMemo(() => initialSourceState(workspace.sources), [workspace.sources])
  const [sourceState, setSourceState] = useState(initialState)
  const [task, setTask] = useState(workspace.task)
  const [actionError, setActionError] = useState<string | null>(null)
  const [connection, setConnection] = useState<RequirementGeneratorState["connection"]>("closed")
  const [pending, startTransition] = useTransition()
  const summaryRef = useRef<HTMLDivElement>(null)
  const idempotencyRef = useRef<{ readonly fingerprint: string; readonly key: string } | null>(null)
  const taskIsActive = task !== null && !terminalStatuses.has(task.status)
  const taskId = task?.id ?? null
  const taskStatus = task?.status ?? null
  const editable = canManage && !archived && workspace.configuration_ready && !taskIsActive
  const selectedSources = workspace.sources.filter(
    (source) => sourceState[source.source_id]?.selected ?? false,
  )
  const totalCharacters = selectedSources.reduce(
    (total, source) => total + unicodeLength(sourceState[source.source_id]?.correctedText ?? ""),
    0,
  )
  const overLimit = totalCharacters > workspace.input_character_limit
  const dirty = workspace.sources.some((source) => {
    const current = sourceState[source.source_id]
    return current?.selected || current?.correctedText !== source.original_text
  })

  useEffect(() => {
    setTask(workspace.task)
  }, [workspace.task])

  useEffect(() => {
    if (taskId === null || taskStatus === null || terminalStatuses.has(taskStatus)) {
      setConnection("closed")
      return
    }
    if (typeof EventSource === "undefined") {
      setConnection("reconnecting")
      return
    }
    setConnection("connecting")
    const source = new EventSource(`/jobs/${jobId}/requirement-parsing-tasks/${taskId}/events`, {
      withCredentials: true,
    })
    source.onopen = () => setConnection("open")
    source.onerror = () => setConnection("reconnecting")
    const receive = (rawEvent: Event) => {
      if (!(rawEvent instanceof MessageEvent) || typeof rawEvent.data !== "string") return
      let payload: unknown
      try {
        payload = JSON.parse(rawEvent.data)
      } catch {
        return
      }
      const parsed = requirementTaskEventSchema.safeParse(payload)
      if (!parsed.success || parsed.data.task_id !== taskId) return
      const event = parsed.data
      setTask((current) =>
        current === null || current.id !== event.task_id
          ? current
          : {
              ...current,
              completed_at: terminalStatuses.has(event.status)
                ? event.created_at
                : current.completed_at,
              error_code: event.error_code,
              next_attempt_at: event.next_attempt_at,
              status: event.status,
              updated_at: event.created_at,
            },
      )
      if (terminalStatuses.has(event.status)) {
        source.close()
        setConnection("closed")
        startTransition(() => router.refresh())
      }
    }
    for (const status of [
      "queued",
      "running",
      "retry_scheduled",
      "cancel_requested",
      "succeeded",
      "failed",
      "cancelled",
    ]) {
      source.addEventListener(status, receive)
    }
    return () => source.close()
  }, [jobId, router, taskId, taskStatus])

  useEffect(() => {
    if (!dirty || !editable) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
    }
    const warnLinkNavigation = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return
      }
      const target = event.target
      const anchor = target instanceof Element ? target.closest("a[href]") : null
      if (anchor === null || window.confirm("尚有未提交的来源修改，确定离开此页面吗？")) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
    }
    window.addEventListener("beforeunload", warn)
    document.addEventListener("click", warnLinkNavigation, true)
    return () => {
      window.removeEventListener("beforeunload", warn)
      document.removeEventListener("click", warnLinkNavigation, true)
    }
  }, [dirty, editable])

  const setCorrectedText = (sourceId: string, value: string) => {
    setSourceState((current) => ({
      ...current,
      [sourceId]: { correctedText: value, selected: current[sourceId]?.selected ?? false },
    }))
    setActionError(null)
  }

  const setSelected = (sourceId: string, selected: boolean) => {
    setSourceState((current) => ({
      ...current,
      [sourceId]: {
        correctedText: current[sourceId]?.correctedText ?? "",
        selected,
      },
    }))
    setActionError(null)
  }

  const refresh = () => {
    startTransition(() => router.refresh())
  }

  const submit = () => {
    setActionError(null)
    if (selectedSources.length === 0) {
      setActionError("至少选择一个来源。")
      summaryRef.current?.focus()
      return
    }
    if (overLimit) {
      setActionError("输入超过字符上限，请取消部分材料或精简修正文案。")
      summaryRef.current?.focus()
      return
    }
    const submittedSources = selectedSources.map((source) => ({
      source_id: source.source_id,
      corrected_text: sourceState[source.source_id]?.correctedText ?? "",
    }))
    const fingerprint = submissionFingerprint(submittedSources)
    if (idempotencyRef.current?.fingerprint !== fingerprint) {
      idempotencyRef.current = { fingerprint, key: crypto.randomUUID() }
    }
    const idempotencyKey = idempotencyRef.current.key
    startTransition(async () => {
      const result = await generateRequirementDraftAction(jobId, idempotencyKey, submittedSources)
      if (result.kind === "error") {
        setActionError(result.message)
        summaryRef.current?.focus()
        return
      }
      setTask(result.task)
      router.refresh()
    })
  }

  const cancel = () => {
    if (task === null) return
    setActionError(null)
    startTransition(async () => {
      const result = await cancelRequirementTaskAction(jobId, task.id)
      if (result.kind === "error") {
        setActionError(result.message)
        summaryRef.current?.focus()
        return
      }
      setTask(result.task)
      router.refresh()
    })
  }

  const value: RequirementGeneratorContextValue = {
    actions: { cancel, refresh, setCorrectedText, setSelected, submit },
    meta: {
      configurationReady: workspace.configuration_ready,
      canCancel: canManage && !archived,
      canManage,
      draft: workspace.draft,
      draftDirty,
      editable,
      inputCharacterLimit: workspace.input_character_limit,
      jobId,
      ...(onDraftDirtyChange === undefined ? {} : { onDraftDirtyChange }),
      overLimit,
      selectedCount: selectedSources.length,
      sources: workspace.sources,
      summaryRef,
      totalCharacters,
    },
    state: { actionError, connection, pending, sourceState, task },
  }

  return <RequirementGeneratorContext value={value}>{children}</RequirementGeneratorContext>
}

function SourceEditors() {
  const { actions, meta, state } = useRequirementGenerator()
  return (
    <FieldGroup>
      {meta.sources.map((source) => {
        const editor = state.sourceState[source.source_id]
        const correctedText = editor?.correctedText ?? ""
        const emptyCorrection = normalizeForCount(correctedText).trim().length === 0
        const materialUnavailable =
          source.source_kind === "job-material" && source.scan_status !== "content_checked"
        const selectionDisabled = !meta.editable || materialUnavailable || emptyCorrection
        return (
          <DataRegion key={source.source_id}>
            <DataRegionContent>
              <FieldSet className="min-w-0">
                <FieldLegend>{source.label}</FieldLegend>
                <Field orientation="horizontal" data-disabled={selectionDisabled || undefined}>
                  <Checkbox
                    aria-invalid={editor?.selected && emptyCorrection ? true : undefined}
                    checked={editor?.selected ?? false}
                    disabled={selectionDisabled}
                    id={`requirement-source-${source.source_id}`}
                    onCheckedChange={(checked) => actions.setSelected(source.source_id, checked)}
                  />
                  <FieldContent>
                    <FieldLabel htmlFor={`requirement-source-${source.source_id}`}>
                      用于生成职位需求草稿
                    </FieldLabel>
                    <FieldDescription>
                      {materialUnavailable
                        ? "材料尚未通过内容检查，当前不可选择。"
                        : emptyCorrection
                          ? "先填写非空修正文案，才能选择此来源。"
                          : `来源标识：${source.source_id}`}
                    </FieldDescription>
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel htmlFor={`requirement-original-${source.source_id}`}>
                    原始提取文本
                  </FieldLabel>
                  <Textarea
                    className="min-h-28 break-words"
                    id={`requirement-original-${source.source_id}`}
                    readOnly
                    value={source.original_text}
                  />
                  <FieldDescription>原文会与实际发送的修正文案分别保留。</FieldDescription>
                </Field>
                <Field data-invalid={editor?.selected && emptyCorrection ? true : undefined}>
                  <FieldHeader>
                    <FieldLabel htmlFor={`requirement-correction-${source.source_id}`}>
                      修正文案
                    </FieldLabel>
                    <FieldCount>
                      {unicodeLength(correctedText).toLocaleString("zh-CN")} 字符
                    </FieldCount>
                  </FieldHeader>
                  <Textarea
                    aria-invalid={editor?.selected && emptyCorrection ? true : undefined}
                    autoComplete="off"
                    className="min-h-36 break-words"
                    disabled={!meta.editable || materialUnavailable}
                    id={`requirement-correction-${source.source_id}`}
                    name={`requirement-correction-${source.source_id}`}
                    onChange={(event) =>
                      actions.setCorrectedText(source.source_id, event.target.value)
                    }
                    value={correctedText}
                  />
                  <FieldError>
                    {editor?.selected && emptyCorrection ? "所选来源的修正文案不能为空。" : null}
                  </FieldError>
                </Field>
              </FieldSet>
            </DataRegionContent>
          </DataRegion>
        )
      })}
    </FieldGroup>
  )
}

function Summary() {
  const { actions, meta, state } = useRequirementGenerator()
  return (
    <DataRegion aria-live="polite" ref={meta.summaryRef} tabIndex={-1}>
      <DataRegionContent>
        <div className="flex flex-wrap items-center justify-between gap-[var(--space-4)]">
          <div className="min-w-0">
            <p className="m-0 font-medium">提交汇总</p>
            <p className="m-0 text-sm text-muted-foreground tabular-nums">
              已选择 {meta.selectedCount.toLocaleString("zh-CN")} 个来源，
              {meta.totalCharacters.toLocaleString("zh-CN")} /{" "}
              {meta.inputCharacterLimit.toLocaleString("zh-CN")} 字符
            </p>
          </div>
          {meta.overLimit ? <Badge variant="destructive">已超限</Badge> : <Badge>未超限</Badge>}
        </div>
        {state.actionError ? (
          <Alert>
            <AlertTitle>无法提交</AlertTitle>
            <AlertDescription>{state.actionError}</AlertDescription>
          </Alert>
        ) : null}
        {!meta.configurationReady ? (
          <Alert>
            <AlertTitle>生成配置尚未就绪</AlertTitle>
            <AlertDescription>
              平台管理员需要通过现有配置探测启用 v2 提示词和 Schema；当前仍可查看来源与历史结果。
            </AlertDescription>
          </Alert>
        ) : null}
        {meta.draft !== null && meta.draftDirty ? (
          <Alert>
            <AlertTitle>草稿还有未保存修改</AlertTitle>
            <AlertDescription>请先保存草稿，或放弃本地修改，再提交重新解析任务。</AlertDescription>
          </Alert>
        ) : null}
      </DataRegionContent>
      {meta.editable ? (
        <DataRegionFooter>
          {meta.draft === null ? (
            <Button
              disabled={state.pending || meta.overLimit}
              onClick={actions.submit}
              type="button"
            >
              {state.pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
              {state.pending ? "正在提交…" : "生成职位需求草稿"}
            </Button>
          ) : (
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button
                    disabled={state.pending || meta.overLimit || meta.draftDirty}
                    type="button"
                  />
                }
              >
                重新解析并替换草稿
              </AlertDialogTrigger>
              <AlertDialogContent size="sm" variant="destructive">
                <AlertDialogHeader showCloseButton={false}>
                  <AlertDialogTitle>重新解析职位需求？</AlertDialogTitle>
                  <AlertDialogDescription>
                    任务成功后会用新草稿替换当前草稿；失败或取消不会修改当前草稿。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogBody>
                  当前修订 {meta.draft.revision} 会保持可编辑，直到新任务成功完成。
                </AlertDialogBody>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={state.pending}>继续编辑</AlertDialogCancel>
                  <AlertDialogAction
                    disabled={state.pending}
                    onClick={actions.submit}
                    type="button"
                    variant="destructive"
                  >
                    {state.pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
                    {state.pending ? "正在提交…" : "确认重新解析"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </DataRegionFooter>
      ) : null}
    </DataRegion>
  )
}

function ConnectionStatus() {
  const { state } = useRequirementGenerator()
  if (state.connection === "closed") return null
  const label =
    state.connection === "open"
      ? "实时状态已连接"
      : state.connection === "reconnecting"
        ? "正在重新连接…"
        : "正在连接实时状态…"
  return (
    <p aria-live="polite" className="m-0 text-sm text-muted-foreground">
      {label}
    </p>
  )
}

function CancelTaskOperation() {
  const { actions, meta, state } = useRequirementGenerator()
  const task = state.task
  if (
    task === null ||
    !meta.canCancel ||
    !["queued", "running", "retry_scheduled"].includes(task.status)
  ) {
    return null
  }
  return (
    <AlertDialog>
      <AlertDialogTrigger render={<Button size="sm" type="button" variant="outline" />}>
        取消任务
      </AlertDialogTrigger>
      <AlertDialogContent size="sm" variant="destructive">
        <AlertDialogHeader showCloseButton={false}>
          <AlertDialogTitle>取消职位需求解析任务？</AlertDialogTitle>
          <AlertDialogDescription>
            已发出的模型调用可能继续完成，但迟到结果不会写入职位需求草稿。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogBody>取消不会修改已经存在的职位需求草稿。</AlertDialogBody>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={state.pending}>继续等待</AlertDialogCancel>
          <AlertDialogAction
            disabled={state.pending}
            onClick={actions.cancel}
            type="button"
            variant="destructive"
          >
            {state.pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
            {state.pending ? "正在取消…" : "确认取消任务"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function TaskStatusBadge({ status }: { readonly status: RequirementTaskStatus }) {
  const variant =
    status === "succeeded"
      ? "success"
      : status === "failed" || status === "cancelled"
        ? "destructive"
        : status === "retry_scheduled" || status === "cancel_requested"
          ? "warning"
          : "info"
  return <Badge variant={variant}>{statusLabels[status]}</Badge>
}

function ActiveTask() {
  const { actions, state } = useRequirementGenerator()
  const task = state.task
  if (task === null || terminalStatuses.has(task.status)) return null
  return (
    <DataRegion aria-live="polite">
      <DataRegionContent>
        <div className="flex flex-wrap items-center justify-between gap-[var(--space-4)]">
          <div className="min-w-0">
            <p className="m-0 font-medium">草稿生成状态</p>
            <p className="m-0 break-words font-mono text-xs text-muted-foreground">
              任务 {task.id}
            </p>
          </div>
          <TaskStatusBadge status={task.status} />
        </div>
        {task.replaces_draft_id !== null ? (
          <Alert>
            <AlertTitle>当前草稿暂时只读</AlertTitle>
            <AlertDescription>
              重新解析任务正在运行。任务成功后会切换到新草稿；失败或取消后恢复编辑。
            </AlertDescription>
          </Alert>
        ) : null}
        {task.error_code ? (
          <Alert>
            <AlertTitle>任务正在恢复</AlertTitle>
            <AlertDescription>
              {taskErrorMessages[task.error_code] ?? "任务暂时不可用，系统会按计划继续处理。"}
            </AlertDescription>
          </Alert>
        ) : null}
        {task.next_attempt_at ? (
          <p className="m-0 text-sm text-muted-foreground tabular-nums">
            下次尝试：
            {taskTimeFormatter.format(new Date(task.next_attempt_at))}
          </p>
        ) : null}
        <p className="m-0 text-sm text-muted-foreground">
          任务已持久化，可以离开或刷新页面；结果会从数据库恢复。
        </p>
        <ConnectionStatus />
      </DataRegionContent>
      <DataRegionFooter className="flex flex-wrap gap-[var(--space-3)]">
        <CancelTaskOperation />
        <Button
          disabled={state.pending}
          onClick={actions.refresh}
          size="sm"
          type="button"
          variant="outline"
        >
          <RefreshCwIcon aria-hidden="true" data-icon="inline-start" />
          刷新状态
        </Button>
      </DataRegionFooter>
    </DataRegion>
  )
}

function TerminalTask() {
  const { actions, state } = useRequirementGenerator()
  const task = state.task
  if (task === null || !terminalStatuses.has(task.status)) return null
  const failure = task.error_code
    ? (taskErrorMessages[task.error_code] ?? "任务失败。请检查来源后重试或联系平台管理员。")
    : null
  return (
    <DataRegion aria-live="polite">
      <DataRegionContent>
        <div className="flex flex-wrap items-center justify-between gap-[var(--space-4)]">
          <div className="min-w-0">
            <p className="m-0 font-medium">草稿生成状态</p>
            <p className="m-0 break-words font-mono text-xs text-muted-foreground">
              任务 {task.id}
            </p>
          </div>
          <TaskStatusBadge status={task.status} />
        </div>
        {failure ? (
          <Alert>
            <AlertTitle>生成未完成</AlertTitle>
            <AlertDescription>{failure}</AlertDescription>
          </Alert>
        ) : null}
      </DataRegionContent>
      <DataRegionFooter>
        <Button
          disabled={state.pending}
          onClick={actions.refresh}
          size="sm"
          type="button"
          variant="outline"
        >
          <RefreshCwIcon aria-hidden="true" data-icon="inline-start" />
          刷新状态
        </Button>
      </DataRegionFooter>
    </DataRegion>
  )
}

function TaskStatus() {
  return (
    <>
      <ActiveTask />
      <TerminalTask />
    </>
  )
}

function DraftEditor() {
  const { meta } = useRequirementGenerator()
  if (meta.draft === null) return null
  return (
    <JobRequirementDraftEditor
      canManage={meta.canManage}
      draft={meta.draft}
      jobId={meta.jobId}
      {...(meta.onDraftDirtyChange === undefined ? {} : { onDirtyChange: meta.onDraftDirtyChange })}
    />
  )
}

export const RequirementGenerator = {
  DraftEditor,
  DraftViewer: DraftEditor,
  Provider: RequirementGeneratorProvider,
  SourceEditors,
  Summary,
  TaskStatus,
}

export function JobRequirementGenerator({
  archived,
  canManage,
  jobId,
  workspace,
}: {
  readonly archived: boolean
  readonly canManage: boolean
  readonly jobId: string
  readonly workspace: RequirementWorkspace
}) {
  const [draftDirty, setDraftDirty] = useState(false)
  return (
    <RequirementGeneratorProvider
      archived={archived}
      canManage={canManage}
      draftDirty={draftDirty}
      jobId={jobId}
      onDraftDirtyChange={setDraftDirty}
      workspace={workspace}
    >
      <div className="flex min-w-0 flex-col gap-[var(--space-5)]">
        <TaskStatus />
        <DraftEditor />
        <SourceEditors />
        <Summary />
      </div>
    </RequirementGeneratorProvider>
  )
}
