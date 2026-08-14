"use client"

import { ChevronDownIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { useRouter } from "next/navigation"
import {
  createContext,
  use,
  useActionState,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react"
import { toast } from "sonner"

import {
  abandonRequirementDraftAction,
  type ConfirmRequirementActionState,
  confirmRequirementDraftAction,
  type RequirementDraftActionState,
  resolveUpgradeLossyItemsAction,
  saveRequirementDraftAction,
  upgradeSchemaAction,
} from "@/app/actions/job-requirements"
import {
  DataRegion,
  DataRegionContent,
  DataRegionFooter,
  DataRegionHeader,
  FormSectionDescription,
  FormSectionTitle,
  PageSectionTitle,
} from "@/components/layout/page"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { truncateLabel } from "@/lib/job-detail-tabs"
import type {
  EditableExecutableCondition,
  EditableUnsupportedCondition,
  PendingUpgradeItem,
  RequirementDraft,
  RequirementDraftSubmission,
  RequirementEvidence,
  SchemaUpgradeResolutionInput,
} from "@/lib/job-requirement-contract"

type ConditionValue = string | number | Array<string | number>
type ConditionSection = "hard_conditions" | "preference_conditions"

type DraftConditionState = {
  readonly localId: string
  readonly itemId: string | null
  readonly origin: "model" | "user_added"
  readonly field: string
  readonly operator: string
  readonly value: ConditionValue
  readonly description: string
  readonly evidence: readonly RequirementEvidence[]
  readonly modelSnapshot: EditableExecutableCondition["model_snapshot"]
  readonly lastModifiedBy: string | null
  readonly lastModifiedAt: string | null
}

type UnsupportedState = {
  readonly localId: string
  readonly itemId: string | null
  readonly origin: "model" | "user_added"
  readonly description: string
  readonly evidence: readonly RequirementEvidence[]
  readonly modelSnapshot: EditableUnsupportedCondition["model_snapshot"]
  readonly lastModifiedBy: string | null
  readonly lastModifiedAt: string | null
}

type ConflictState = {
  readonly itemId: string
  readonly description: string
  readonly evidence: readonly RequirementEvidence[]
  readonly resolved: boolean
  readonly resolutionNote: string
}

type DraftEditorState = {
  readonly hardConditions: readonly DraftConditionState[]
  readonly preferenceConditions: readonly DraftConditionState[]
  readonly researchTopicQuery: string
  readonly unsupportedConditions: readonly UnsupportedState[]
  readonly sourceConflicts: readonly ConflictState[]
}

type DraftEditorActions = {
  readonly setResearchTopicQuery: (value: string) => void
  readonly addPreferenceCondition: () => void
  readonly updateCondition: (
    section: ConditionSection,
    localId: string,
    patch: Partial<Pick<DraftConditionState, "description" | "field" | "operator" | "value">>,
  ) => void
  readonly changeConditionField: (section: ConditionSection, localId: string, field: string) => void
  readonly changeConditionOperator: (
    section: ConditionSection,
    localId: string,
    operator: string,
  ) => void
  readonly moveCondition: (section: ConditionSection, localId: string) => void
  readonly removeCondition: (section: ConditionSection, localId: string) => void
  readonly updateUnsupported: (localId: string, description: string) => void
  readonly removeUnsupported: (localId: string) => void
  readonly setConflictResolved: (itemId: string, resolved: boolean) => void
  readonly setConflictNote: (itemId: string, note: string) => void
  readonly validateBeforeSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  readonly abandon: () => void
  readonly confirm: () => void
  readonly upgradeSchema: () => void
  readonly resolveUpgrades: (resolutions: readonly SchemaUpgradeResolutionInput[]) => void
}

type DraftEditorMeta = {
  readonly draft: RequirementDraft
  readonly canEdit: boolean
  readonly dirty: boolean
  readonly pending: boolean
  readonly abandoning: boolean
  readonly confirming: boolean
  readonly upgrading: boolean
  readonly resolving: boolean
  readonly confirmBlockedReason: string | null
  readonly errors: Readonly<Record<string, string>>
  readonly feedback: RequirementDraftActionState | ConfirmRequirementActionState
  readonly feedbackRef: React.RefObject<HTMLDivElement | null>
  readonly formAction: (payload: FormData) => void
  readonly submission: RequirementDraftSubmission
}

type DraftEditorContextValue = {
  readonly state: DraftEditorState
  readonly actions: DraftEditorActions
  readonly meta: DraftEditorMeta
}

const RequirementDraftEditorContext = createContext<DraftEditorContextValue | null>(null)
const idleActionState: RequirementDraftActionState = { kind: "idle" }

const fieldLabels: Readonly<Record<string, string>> = {
  qs_top200_rank: "QS 前 200 排名",
  world_top500_rank: "世界前 500 排名",
  h_index: "H 指数",
  total_citations: "总引用数",
  chinese_identity: "华人身份",
  country: "国家",
  current_affiliation: "当前任职机构",
}

const operatorLabels: Readonly<Record<string, string>> = {
  gte: "大于或等于",
  lte: "小于或等于",
  between: "区间",
  eq: "等于",
  in: "包含任一值",
  match: "文本匹配",
  match_phrase: "短语匹配",
}

const numericFields = new Set(["qs_top200_rank", "world_top500_rank", "h_index", "total_citations"])

function useRequirementDraftEditor(): DraftEditorContextValue {
  const context = use(RequirementDraftEditorContext)
  if (context === null) {
    throw new Error("RequirementDraftEditor components require RequirementDraftEditor.Provider")
  }
  return context
}

function conditionState(condition: EditableExecutableCondition): DraftConditionState {
  return {
    localId: condition.item_id,
    itemId: condition.item_id,
    origin: condition.origin,
    field: condition.field,
    operator: condition.operator,
    value: condition.value,
    description: condition.description,
    evidence: condition.evidence,
    modelSnapshot: condition.model_snapshot,
    lastModifiedBy: condition.last_modified_by,
    lastModifiedAt: condition.last_modified_at,
  }
}

function editorStateFromDraft(draft: RequirementDraft): DraftEditorState {
  return {
    hardConditions: draft.result.hard_conditions.map(conditionState),
    preferenceConditions: draft.result.preference_conditions.map(conditionState),
    researchTopicQuery: draft.result.research_topic_query.value,
    unsupportedConditions: draft.result.unsupported_conditions.map((condition) => ({
      localId: condition.item_id,
      itemId: condition.item_id,
      origin: condition.origin,
      description: condition.description,
      evidence: condition.evidence,
      modelSnapshot: condition.model_snapshot,
      lastModifiedBy: condition.last_modified_by,
      lastModifiedAt: condition.last_modified_at,
    })),
    sourceConflicts: draft.result.source_conflicts.map((conflict) => ({
      itemId: conflict.item_id,
      description: conflict.description,
      evidence: conflict.evidence,
      resolved: conflict.resolution !== null,
      resolutionNote: conflict.resolution?.note ?? "",
    })),
  }
}

function submissionFromState(state: DraftEditorState): RequirementDraftSubmission {
  const condition = (item: DraftConditionState) => ({
    item_id: item.itemId,
    field: item.field,
    operator: item.operator,
    value: normalizeSubmittedValue(item),
    description: item.description,
  })
  return {
    hard_conditions: state.hardConditions.map(condition),
    preference_conditions: state.preferenceConditions.map(condition),
    research_topic_query: state.researchTopicQuery,
    unsupported_conditions: state.unsupportedConditions.map((item) => ({
      item_id: item.itemId,
      description: item.description,
    })),
    source_conflicts: state.sourceConflicts.map((item) => ({
      item_id: item.itemId,
      resolution_note: item.resolved ? item.resolutionNote : null,
    })),
  }
}

function normalizeSubmittedValue(item: DraftConditionState): unknown {
  if (numericFields.has(item.field)) {
    if (item.operator === "between" && Array.isArray(item.value)) {
      return item.value.map((value) => (value === "" ? value : Number(value)))
    }
    return item.value === "" ? item.value : Number(item.value)
  }
  if (item.field === "country" && item.operator === "in") {
    const values = Array.isArray(item.value)
      ? item.value.map(String)
      : String(item.value).split(/[，,\n]/)
    return values.map((value) => value.trim()).filter(Boolean)
  }
  if (item.operator === "in") {
    return Array.isArray(item.value) ? item.value : [item.value]
  }
  return Array.isArray(item.value) ? (item.value[0] ?? "") : item.value
}

function RequirementDraftEditorProvider({
  canManage,
  children,
  draft: initialDraft,
  jobId,
  onDirtyChange,
}: {
  readonly canManage: boolean
  readonly children: React.ReactNode
  readonly draft: RequirementDraft
  readonly jobId: string
  readonly onDirtyChange?: (dirty: boolean) => void
}) {
  const router = useRouter()
  const [draft, setDraft] = useState(initialDraft)
  const [state, setState] = useState(() => editorStateFromDraft(initialDraft))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [abandonFeedback, setAbandonFeedback] = useState<RequirementDraftActionState | null>(null)
  const [confirmFeedback, setConfirmFeedback] = useState<ConfirmRequirementActionState | null>(null)
  const [resolveFeedback, setResolveFeedback] = useState<RequirementDraftActionState | null>(null)
  const [abandoning, startAbandonTransition] = useTransition()
  const [confirming, startConfirmTransition] = useTransition()
  const [upgrading, startUpgradeTransition] = useTransition()
  const [resolving, startResolveTransition] = useTransition()
  const feedbackRef = useRef<HTMLDivElement>(null)
  const baselineRef = useRef(
    JSON.stringify(submissionFromState(editorStateFromDraft(initialDraft))),
  )
  const saveAction = useMemo(
    () => saveRequirementDraftAction.bind(null, jobId, draft.id),
    [draft.id, jobId],
  )
  const [saveFeedback, formAction, pending] = useActionState(saveAction, idleActionState)
  const submission = submissionFromState(state)
  const dirty = JSON.stringify(submission) !== baselineRef.current
  const canEdit = canManage && draft.status === "editable" && draft.read_only_reason === null
  const feedback = confirmFeedback ?? abandonFeedback ?? resolveFeedback ?? saveFeedback
  const unresolvedConflicts = state.sourceConflicts.filter((item) => !item.resolved)
  const confirmBlockedReason = !canEdit
    ? "当前草稿不可确认。"
    : dirty
      ? "请先保存草稿，再确认版本。"
      : !state.researchTopicQuery.trim()
        ? "研究主题查询不能为空。"
        : unresolvedConflicts.length > 0
          ? `还有 ${unresolvedConflicts.length} 个来源冲突未解决。`
          : draft.pending_upgrade_items.length > 0
            ? "存在待解决的升级项，处理完成后才能确认"
            : null

  useEffect(() => {
    if (initialDraft.id === draft.id) {
      if (initialDraft.revision < draft.revision) return
      if (initialDraft.revision === draft.revision) {
        if (
          initialDraft.status !== draft.status ||
          initialDraft.read_only_reason !== draft.read_only_reason
        ) {
          setDraft(initialDraft)
        }
        return
      }
    }
    const next = editorStateFromDraft(initialDraft)
    setDraft(initialDraft)
    setState(next)
    baselineRef.current = JSON.stringify(submissionFromState(next))
    setErrors({})
  }, [draft.id, draft.read_only_reason, draft.revision, draft.status, initialDraft])

  useEffect(() => {
    if (saveFeedback.kind !== "ok" && saveFeedback.kind !== "revisionConflict") return
    const next = editorStateFromDraft(saveFeedback.draft)
    setDraft(saveFeedback.draft)
    setState(next)
    baselineRef.current = JSON.stringify(submissionFromState(next))
    setErrors({})
    onDirtyChange?.(false)
    feedbackRef.current?.focus()
    router.refresh()
  }, [onDirtyChange, router, saveFeedback])

  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])

  useEffect(() => {
    if (!dirty || !canEdit) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
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
      if (anchor === null || window.confirm("职位需求草稿尚未保存，确定离开此页面吗？")) {
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
  }, [canEdit, dirty])

  const updateCondition = (
    section: ConditionSection,
    localId: string,
    patch: Partial<Pick<DraftConditionState, "description" | "field" | "operator" | "value">>,
  ) => {
    const key = section === "hard_conditions" ? "hardConditions" : "preferenceConditions"
    setState((current) => ({
      ...current,
      [key]: current[key].map((item) => (item.localId === localId ? { ...item, ...patch } : item)),
    }))
    setErrors((current) => {
      const next = { ...current }
      delete next[localId]
      return next
    })
  }

  const changeConditionField = (section: ConditionSection, localId: string, field: string) => {
    const operator = draft.field_catalog[field]?.[0] ?? ""
    updateCondition(section, localId, {
      field,
      operator,
      value: defaultValue(field, operator, draft.chinese_identity_values),
    })
  }

  const changeConditionOperator = (
    section: ConditionSection,
    localId: string,
    operator: string,
  ) => {
    const key = section === "hard_conditions" ? "hardConditions" : "preferenceConditions"
    const item = state[key].find((candidate) => candidate.localId === localId)
    if (item === undefined) return
    updateCondition(section, localId, {
      operator,
      value: valueForOperator(item.value, item.field, operator, draft.chinese_identity_values),
    })
  }

  const moveCondition = (section: ConditionSection, localId: string) => {
    setState((current) => {
      const sourceKey = section === "hard_conditions" ? "hardConditions" : "preferenceConditions"
      const targetKey = section === "hard_conditions" ? "preferenceConditions" : "hardConditions"
      const item = current[sourceKey].find((candidate) => candidate.localId === localId)
      if (item === undefined) return current
      return {
        ...current,
        [sourceKey]: current[sourceKey].filter((candidate) => candidate.localId !== localId),
        [targetKey]: [...current[targetKey], item],
      }
    })
  }

  const removeCondition = (section: ConditionSection, localId: string) => {
    const key = section === "hard_conditions" ? "hardConditions" : "preferenceConditions"
    setState((current) => ({
      ...current,
      [key]: current[key].filter((item) => item.localId !== localId),
    }))
  }

  const addPreferenceCondition = () => {
    const field = Object.keys(draft.field_catalog)[0] ?? "h_index"
    const operator = draft.field_catalog[field]?.[0] ?? "gte"
    setState((current) => {
      if (current.hardConditions.length + current.preferenceConditions.length >= 100) {
        return current
      }
      return {
        ...current,
        preferenceConditions: [
          ...current.preferenceConditions,
          {
            localId: `new-${crypto.randomUUID()}`,
            itemId: null,
            origin: "user_added",
            field,
            operator,
            value: defaultValue(field, operator, draft.chinese_identity_values),
            description: "",
            evidence: [],
            modelSnapshot: null,
            lastModifiedBy: null,
            lastModifiedAt: null,
          },
        ],
      }
    })
  }

  const validateBeforeSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    setAbandonFeedback(null)
    setConfirmFeedback(null)
    const nextErrors = validateEditor(state, draft)
    if (Object.keys(nextErrors).length === 0) return
    event.preventDefault()
    setErrors(nextErrors)
    const firstId = Object.keys(nextErrors)[0]
    if (firstId !== undefined) {
      document.getElementById(`draft-field-${firstId}`)?.focus()
    }
  }

  const abandon = () => {
    startAbandonTransition(async () => {
      setConfirmFeedback(null)
      const result = await abandonRequirementDraftAction(jobId, draft.id, draft.revision)
      setAbandonFeedback(result)
      if (result.kind === "revisionConflict") {
        const next = editorStateFromDraft(result.draft)
        setDraft(result.draft)
        setState(next)
        baselineRef.current = JSON.stringify(submissionFromState(next))
        onDirtyChange?.(false)
      }
      if (result.kind === "ok") {
        const next = editorStateFromDraft(result.draft)
        setDraft(result.draft)
        setState(next)
        baselineRef.current = JSON.stringify(submissionFromState(next))
        onDirtyChange?.(false)
        router.refresh()
      }
      feedbackRef.current?.focus()
    })
  }

  const confirm = () => {
    if (confirmBlockedReason !== null) return
    startConfirmTransition(async () => {
      setAbandonFeedback(null)
      const result = await confirmRequirementDraftAction(jobId, draft.id, draft.revision)
      setConfirmFeedback(result)
      if (result.kind === "revisionConflict") {
        const next = editorStateFromDraft(result.draft)
        setDraft(result.draft)
        setState(next)
        baselineRef.current = JSON.stringify(submissionFromState(next))
        onDirtyChange?.(false)
      }
      if (result.kind === "ok") {
        const next = editorStateFromDraft(result.draft)
        setDraft(result.draft)
        setState(next)
        baselineRef.current = JSON.stringify(submissionFromState(next))
        onDirtyChange?.(false)
        router.refresh()
      }
      feedbackRef.current?.focus()
    })
  }

  const applyServerDraft = (nextDraft: RequirementDraft) => {
    const next = editorStateFromDraft(nextDraft)
    setDraft(nextDraft)
    setState(next)
    baselineRef.current = JSON.stringify(submissionFromState(next))
    setErrors({})
    onDirtyChange?.(false)
  }

  const upgradeSchema = () => {
    if (!canEdit || dirty || draft.pending_upgrade_items.length > 0) return
    startUpgradeTransition(async () => {
      setAbandonFeedback(null)
      setConfirmFeedback(null)
      setResolveFeedback(null)
      const result = await upgradeSchemaAction(jobId, draft.id, draft.revision)
      if (result.kind === "ok") {
        applyServerDraft(result.draft)
        toast.success(result.message)
      } else if (result.kind !== "idle") {
        if (result.kind === "revisionConflict") applyServerDraft(result.draft)
        toast.error(result.message)
      }
      router.refresh()
    })
  }

  const resolveUpgrades = (resolutions: readonly SchemaUpgradeResolutionInput[]) => {
    if (!canEdit || resolutions.length === 0) return
    startResolveTransition(async () => {
      setAbandonFeedback(null)
      setConfirmFeedback(null)
      const result = await resolveUpgradeLossyItemsAction(
        jobId,
        draft.id,
        draft.revision,
        resolutions,
      )
      setResolveFeedback(result)
      if (result.kind === "ok" || result.kind === "revisionConflict") {
        applyServerDraft(result.draft)
        router.refresh()
      }
      feedbackRef.current?.focus()
    })
  }

  const value: DraftEditorContextValue = {
    state,
    actions: {
      abandon,
      confirm,
      resolveUpgrades,
      upgradeSchema,
      addPreferenceCondition,
      changeConditionField,
      changeConditionOperator,
      moveCondition,
      removeCondition,
      removeUnsupported: (localId) =>
        setState((current) => ({
          ...current,
          unsupportedConditions: current.unsupportedConditions.filter(
            (item) => item.localId !== localId,
          ),
        })),
      setConflictNote: (itemId, note) =>
        setState((current) => ({
          ...current,
          sourceConflicts: current.sourceConflicts.map((item) =>
            item.itemId === itemId ? { ...item, resolutionNote: note } : item,
          ),
        })),
      setConflictResolved: (itemId, resolved) =>
        setState((current) => ({
          ...current,
          sourceConflicts: current.sourceConflicts.map((item) =>
            item.itemId === itemId ? { ...item, resolved } : item,
          ),
        })),
      setResearchTopicQuery: (researchTopicQuery) =>
        setState((current) => ({ ...current, researchTopicQuery })),
      updateCondition,
      updateUnsupported: (localId, description) =>
        setState((current) => ({
          ...current,
          unsupportedConditions: current.unsupportedConditions.map((item) =>
            item.localId === localId ? { ...item, description } : item,
          ),
        })),
      validateBeforeSubmit,
    },
    meta: {
      abandoning,
      confirming,
      confirmBlockedReason,
      canEdit,
      dirty,
      draft,
      errors,
      feedback,
      feedbackRef,
      formAction,
      pending,
      resolving,
      submission,
      upgrading,
    },
  }

  return <RequirementDraftEditorContext value={value}>{children}</RequirementDraftEditorContext>
}

function EditorFrame({ children }: { readonly children: React.ReactNode }) {
  const { actions, meta } = useRequirementDraftEditor()
  return (
    <form
      action={meta.formAction}
      className="flex min-w-0 flex-col gap-8"
      onSubmit={actions.validateBeforeSubmit}
    >
      <input name="expected_revision" type="hidden" value={meta.draft.revision} />
      <input name="result" type="hidden" value={JSON.stringify(meta.submission)} />
      {children}
    </form>
  )
}

function EditorHeader() {
  const { meta, state } = useRequirementDraftEditor()
  const unresolved = state.sourceConflicts.filter((conflict) => !conflict.resolved).length
  const pendingUpgrades = meta.draft.pending_upgrade_items.length
  const hasNotices =
    meta.draft.read_only_reason === "replacement_in_progress" ||
    meta.draft.read_only_reason === "job_archived" ||
    (!meta.canEdit && meta.draft.read_only_reason === null)
  return (
    <DataRegion>
      <DataRegionHeader className={hasNotices ? undefined : "border-b-0"}>
        <div className="min-w-0">
          <PageSectionTitle>审阅职位需求草稿</PageSectionTitle>
          <p className="m-0 text-sm text-muted-foreground tabular-nums" translate="no">
            Schema {meta.draft.requirement_schema_version_id}，修订 {meta.draft.revision}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {meta.dirty ? <Badge variant="warning">有未保存修改</Badge> : <Badge>已保存</Badge>}
          {unresolved > 0 ? (
            <Badge variant="warning">{unresolved} 个冲突未解决</Badge>
          ) : (
            <Badge variant="success">冲突已处理</Badge>
          )}
          {pendingUpgrades > 0 ? (
            <Badge variant="warning">{pendingUpgrades} 个升级项待解决</Badge>
          ) : null}
          {meta.canEdit ? <UpgradeSchemaButton /> : null}
        </div>
      </DataRegionHeader>
      {hasNotices ? (
        <DataRegionContent className="flex flex-col gap-3 px-5 py-4">
          {meta.draft.read_only_reason === "replacement_in_progress" ? (
            <Alert>
              <AlertTitle>重新解析正在进行</AlertTitle>
              <AlertDescription>
                当前草稿暂时只读。任务成功后会切换到新草稿，失败或取消后恢复编辑。
              </AlertDescription>
            </Alert>
          ) : null}
          {meta.draft.read_only_reason === "job_archived" ? (
            <Alert>
              <AlertTitle>职位已归档</AlertTitle>
              <AlertDescription>归档职位只能查看历史草稿，不能编辑或放弃。</AlertDescription>
            </Alert>
          ) : null}
          {!meta.canEdit && meta.draft.read_only_reason === null ? (
            <p className="m-0 text-sm text-muted-foreground">
              你可以查看完整草稿，但没有管理权限。
            </p>
          ) : null}
        </DataRegionContent>
      ) : null}
    </DataRegion>
  )
}

function UpgradeSchemaButton() {
  const { actions, meta } = useRequirementDraftEditor()
  const blocked =
    meta.pending ||
    meta.abandoning ||
    meta.confirming ||
    meta.resolving ||
    meta.upgrading ||
    meta.dirty ||
    meta.draft.pending_upgrade_items.length > 0
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={<Button disabled={blocked} size="sm" type="button" variant="outline" />}
      >
        升级 Schema
      </AlertDialogTrigger>
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogTitle>升级草稿 Schema？</AlertDialogTitle>
          <AlertDialogDescription>
            将使用确定性转换器把草稿升级到当前 Schema 版本，不调用模型重新解析。
            无法无损转换的条件会列为待解决升级项，处理完成后才能确认版本。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={meta.upgrading}>取消</AlertDialogCancel>
          <AlertDialogAction onClick={actions.upgradeSchema} pending={meta.upgrading} type="button">
            {meta.upgrading ? "正在升级…" : "确认升级"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function PendingUpgradeItemCard({
  choice,
  item,
  onChoiceChange,
}: {
  readonly choice: SchemaUpgradeResolutionInput["resolution"]
  readonly item: PendingUpgradeItem
  readonly onChoiceChange: (resolution: SchemaUpgradeResolutionInput["resolution"]) => void
}) {
  const { meta } = useRequirementDraftEditor()
  const snapshot = item.snapshot
  return (
    <DataRegion>
      <DataRegionContent className="flex flex-col gap-3 px-5 py-4">
        <p className="m-0 break-words font-medium">
          {item.kind === "hard_condition" ? "硬条件" : "偏好条件"} · {snapshot.description}
        </p>
        <p className="m-0 text-sm text-muted-foreground" translate="no">
          {fieldLabels[snapshot.field] ?? snapshot.field} ·{" "}
          {operatorLabels[snapshot.operator] ?? snapshot.operator} ·{" "}
          {formatConditionValue(snapshot.value)}
        </p>
        <RadioGroup
          disabled={!meta.canEdit}
          name={`upgrade-resolution-${item.item_id}`}
          onValueChange={(value) => {
            if (value === "drop" || value === "downgrade_unsupported") onChoiceChange(value)
          }}
          value={choice}
        >
          <label
            className="flex min-h-11 items-center gap-3 text-sm"
            htmlFor={`upgrade-downgrade-${item.item_id}`}
          >
            <RadioGroupItem
              id={`upgrade-downgrade-${item.item_id}`}
              value="downgrade_unsupported"
            />
            转为未支持条件
          </label>
          <label
            className="flex min-h-11 items-center gap-3 text-sm"
            htmlFor={`upgrade-drop-${item.item_id}`}
          >
            <RadioGroupItem id={`upgrade-drop-${item.item_id}`} value="drop" />
            丢弃
          </label>
        </RadioGroup>
      </DataRegionContent>
    </DataRegion>
  )
}

function PendingUpgradeSection() {
  const { actions, meta } = useRequirementDraftEditor()
  const [choices, setChoices] = useState<
    Readonly<Record<string, SchemaUpgradeResolutionInput["resolution"]>>
  >({})
  const items = meta.draft.pending_upgrade_items
  if (items.length === 0) return null
  const submit = () => {
    actions.resolveUpgrades(
      items.map((item) => ({
        item_id: item.item_id,
        resolution: choices[item.item_id] ?? "downgrade_unsupported",
      })),
    )
  }
  return (
    <section aria-labelledby="draft-upgrade-heading" className="flex min-w-0 flex-col gap-4">
      <div className="min-w-0">
        <FormSectionTitle id="draft-upgrade-heading">
          待解决升级项 · {items.length.toLocaleString("zh-CN")} 条
        </FormSectionTitle>
        <FormSectionDescription>
          Schema 升级无法无损转换以下条件。逐条选择处理方式并提交，处理完成后才能确认版本。
        </FormSectionDescription>
      </div>
      {items.map((item) => (
        <PendingUpgradeItemCard
          choice={choices[item.item_id] ?? "downgrade_unsupported"}
          item={item}
          key={item.item_id}
          onChoiceChange={(resolution) =>
            setChoices((current) => ({ ...current, [item.item_id]: resolution }))
          }
        />
      ))}
      {meta.canEdit ? (
        <div>
          <Button disabled={meta.resolving} onClick={submit} type="button">
            {meta.resolving ? "正在提交…" : "提交处理方式"}
          </Button>
        </div>
      ) : (
        <p className="m-0 text-sm text-muted-foreground">
          存在待解决的升级项，需要具有管理权限的成员处理。
        </p>
      )}
    </section>
  )
}

function ResearchTopicSection() {
  const { actions, meta, state } = useRequirementDraftEditor()
  const error = meta.errors["research_topic_query"]
  const modelValue = meta.draft.result.research_topic_query.model_value
  return (
    <DataRegion>
      <DataRegionContent className="flex flex-col gap-4 px-5 py-4">
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="draft-field-research_topic_query">研究主题查询</FieldLabel>
          <FieldDescription>用于论文召回与相关性评分。</FieldDescription>
          <Textarea
            aria-invalid={error ? true : undefined}
            autoComplete="off"
            className="min-h-28"
            disabled={!meta.canEdit}
            id="draft-field-research_topic_query"
            maxLength={4000}
            name="research_topic_query"
            onChange={(event) => actions.setResearchTopicQuery(event.target.value)}
            required
            value={state.researchTopicQuery}
          />
          <Collapsible className="flex min-w-0 flex-col gap-2">
            <CollapsibleTrigger
              render={<Button className="w-fit justify-start px-0" size="sm" variant="link" />}
            >
              查看模型原值
              <ChevronDownIcon aria-hidden="true" data-icon="inline-end" data-slot="chevron" />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <FieldDescription className="break-words">{modelValue}</FieldDescription>
            </CollapsibleContent>
          </Collapsible>
          <FieldError>{error}</FieldError>
        </Field>
      </DataRegionContent>
    </DataRegion>
  )
}

function ConditionsSection({
  section,
  title,
}: {
  readonly section: ConditionSection
  readonly title: string
}) {
  const { actions, meta, state } = useRequirementDraftEditor()
  const conditions =
    section === "hard_conditions" ? state.hardConditions : state.preferenceConditions
  const conditionLimitReached =
    state.hardConditions.length + state.preferenceConditions.length >= 100
  const isPreference = section === "preference_conditions"
  const showHeaderAdd = isPreference && meta.canEdit && conditions.length > 0
  return (
    <section aria-labelledby={`draft-${section}-heading`} className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <FormSectionTitle id={`draft-${section}-heading`}>{title}</FormSectionTitle>
          <FormSectionDescription>
            {section === "hard_conditions"
              ? "所有条件同时满足，否则排除。"
              : "不排除人才，仅参与确定性评分。"}
          </FormSectionDescription>
        </div>
        {showHeaderAdd ? (
          <Button
            disabled={conditionLimitReached}
            onClick={actions.addPreferenceCondition}
            size="sm"
            type="button"
            variant="outline"
          >
            <PlusIcon aria-hidden="true" data-icon="inline-start" />
            添加条件
          </Button>
        ) : null}
      </div>
      {conditions.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>{isPreference ? "暂无偏好条件" : "暂无硬条件"}</EmptyTitle>
            <EmptyDescription>
              {isPreference
                ? "添加偏好条件后，它们只参与确定性评分，不会排除人才。"
                : "硬条件会排除不满足的人才。可从偏好条件迁移，或等待重新解析生成。"}
            </EmptyDescription>
          </EmptyHeader>
          {isPreference && meta.canEdit ? (
            <EmptyContent>
              <Button
                disabled={conditionLimitReached}
                onClick={actions.addPreferenceCondition}
                size="sm"
                type="button"
              >
                <PlusIcon aria-hidden="true" data-icon="inline-start" />
                添加条件
              </Button>
            </EmptyContent>
          ) : null}
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {conditions.map((condition) => (
            <ConditionEditor condition={condition} key={condition.localId} section={section} />
          ))}
        </div>
      )}
    </section>
  )
}

function ConditionEditor({
  condition,
  section,
}: {
  readonly condition: DraftConditionState
  readonly section: ConditionSection
}) {
  const { actions, meta } = useRequirementDraftEditor()
  const error = meta.errors[condition.localId]
  const operators = meta.draft.field_catalog[condition.field] ?? []
  return (
    <DataRegion>
      <DataRegionContent className="flex flex-col gap-4 px-5 py-4">
        <FieldSet disabled={!meta.canEdit}>
          <FieldLegend className="flex flex-wrap items-center gap-2">
            {condition.origin === "model" ? "模型提取条件" : "成员新增条件"}
            {condition.lastModifiedBy ? <Badge variant="outline">已人工修改</Badge> : null}
          </FieldLegend>
          <FieldGroup className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel htmlFor={`draft-field-${condition.localId}`}>字段</FieldLabel>
              <Select
                disabled={!meta.canEdit}
                name={`condition-field-${condition.localId}`}
                onValueChange={(value) => {
                  if (typeof value === "string")
                    actions.changeConditionField(section, condition.localId, value)
                }}
                value={condition.field}
              >
                <SelectTrigger id={`draft-field-${condition.localId}`}>
                  <SelectValue>{fieldLabels[condition.field] ?? condition.field}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {Object.keys(meta.draft.field_catalog).map((field) => (
                      <SelectItem key={field} value={field}>
                        {fieldLabels[field] ?? field}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor={`draft-operator-${condition.localId}`}>操作符</FieldLabel>
              <Select
                disabled={!meta.canEdit}
                name={`condition-operator-${condition.localId}`}
                onValueChange={(value) => {
                  if (typeof value === "string")
                    actions.changeConditionOperator(section, condition.localId, value)
                }}
                value={condition.operator}
              >
                <SelectTrigger id={`draft-operator-${condition.localId}`}>
                  <SelectValue>
                    {operatorLabels[condition.operator] ?? condition.operator}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {operators.map((operator) => (
                      <SelectItem key={operator} value={operator}>
                        {operatorLabels[operator] ?? operator}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>
          <ConditionValueEditor condition={condition} section={section} />
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor={`draft-description-${condition.localId}`}>
              条件说明 ·{" "}
              {truncateLabel(
                condition.description || fieldLabels[condition.field] || condition.field,
              )}
            </FieldLabel>
            <Input
              aria-invalid={error ? true : undefined}
              autoComplete="off"
              disabled={!meta.canEdit}
              id={`draft-description-${condition.localId}`}
              maxLength={2000}
              name={`condition-description-${condition.localId}`}
              onChange={(event) =>
                actions.updateCondition(section, condition.localId, {
                  description: event.target.value,
                })
              }
              value={condition.description}
            />
            <FieldError>{error}</FieldError>
          </Field>
          <Provenance condition={condition} />
        </FieldSet>
      </DataRegionContent>
      {meta.canEdit ? (
        <DataRegionFooter className="flex flex-wrap gap-2">
          <Button
            onClick={() => actions.moveCondition(section, condition.localId)}
            size="sm"
            type="button"
            variant="outline"
          >
            {section === "hard_conditions" ? "移到偏好条件" : "移到硬条件"}
          </Button>
          <Button
            onClick={() => actions.removeCondition(section, condition.localId)}
            size="sm"
            type="button"
            variant="ghost"
          >
            <Trash2Icon aria-hidden="true" data-icon="inline-start" />
            删除
          </Button>
        </DataRegionFooter>
      ) : null}
    </DataRegion>
  )
}

function ConditionValueEditor({
  condition,
  section,
}: {
  readonly condition: DraftConditionState
  readonly section: ConditionSection
}) {
  const { actions, meta } = useRequirementDraftEditor()
  const update = (value: ConditionValue) =>
    actions.updateCondition(section, condition.localId, { value })
  if (numericFields.has(condition.field)) {
    if (condition.operator === "between") {
      const values = Array.isArray(condition.value)
        ? condition.value
        : [condition.value, condition.value]
      return (
        <FieldGroup className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[0, 1].map((index) => (
            <Field key={index}>
              <FieldLabel htmlFor={`draft-value-${condition.localId}-${index}`}>
                {index === 0 ? "下限" : "上限"}
              </FieldLabel>
              <Input
                autoComplete="off"
                disabled={!meta.canEdit}
                id={`draft-value-${condition.localId}-${index}`}
                min={0}
                name={`condition-value-${condition.localId}-${index}`}
                onChange={(event) => {
                  const next = [...values]
                  next[index] = event.target.value
                  update(next)
                }}
                type="number"
                value={values[index] ?? ""}
              />
            </Field>
          ))}
        </FieldGroup>
      )
    }
    return (
      <Field>
        <FieldLabel htmlFor={`draft-value-${condition.localId}`}>数值</FieldLabel>
        <Input
          autoComplete="off"
          disabled={!meta.canEdit}
          id={`draft-value-${condition.localId}`}
          min={0}
          name={`condition-value-${condition.localId}`}
          onChange={(event) => update(event.target.value)}
          type="number"
          value={Array.isArray(condition.value) ? (condition.value[0] ?? "") : condition.value}
        />
      </Field>
    )
  }
  if (condition.field === "chinese_identity") {
    if (condition.operator === "in") {
      const selected = new Set(
        Array.isArray(condition.value) ? condition.value.map(String) : [String(condition.value)],
      )
      return (
        <FieldSet>
          <FieldLegend variant="label">允许的华人身份</FieldLegend>
          <FieldGroup>
            {meta.draft.chinese_identity_values.map((identity) => (
              <Field key={identity} orientation="horizontal">
                <Checkbox
                  checked={selected.has(identity)}
                  disabled={!meta.canEdit}
                  id={`draft-value-${condition.localId}-${identity}`}
                  name={`condition-value-${condition.localId}`}
                  onCheckedChange={(checked) => {
                    const next = new Set(selected)
                    if (checked) next.add(identity)
                    else next.delete(identity)
                    update([...next])
                  }}
                />
                <FieldLabel htmlFor={`draft-value-${condition.localId}-${identity}`}>
                  {identity}
                </FieldLabel>
              </Field>
            ))}
          </FieldGroup>
        </FieldSet>
      )
    }
    const selected = Array.isArray(condition.value)
      ? String(condition.value[0] ?? "")
      : String(condition.value)
    return (
      <Field>
        <FieldLabel htmlFor={`draft-value-${condition.localId}`}>华人身份</FieldLabel>
        <Select
          disabled={!meta.canEdit}
          name={`condition-value-${condition.localId}`}
          onValueChange={(value) => {
            if (typeof value === "string") update(value)
          }}
          value={selected}
        >
          <SelectTrigger id={`draft-value-${condition.localId}`}>
            <SelectValue>{selected}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {meta.draft.chinese_identity_values.map((identity) => (
                <SelectItem key={identity} value={identity}>
                  {identity}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
    )
  }
  if (condition.field === "country" && condition.operator === "in") {
    const value = Array.isArray(condition.value)
      ? condition.value.join("\n")
      : String(condition.value)
    return (
      <Field>
        <FieldLabel htmlFor={`draft-value-${condition.localId}`}>国家列表</FieldLabel>
        <Textarea
          autoComplete="off"
          disabled={!meta.canEdit}
          id={`draft-value-${condition.localId}`}
          name={`condition-value-${condition.localId}`}
          onChange={(event) => update(event.target.value)}
          value={value}
        />
        <FieldDescription>每行或使用逗号分隔一个国家。</FieldDescription>
      </Field>
    )
  }
  return (
    <Field>
      <FieldLabel htmlFor={`draft-value-${condition.localId}`}>
        {condition.field === "country" ? "国家" : "机构名称"}
      </FieldLabel>
      <Input
        autoComplete="off"
        disabled={!meta.canEdit}
        id={`draft-value-${condition.localId}`}
        name={`condition-value-${condition.localId}`}
        onChange={(event) => update(event.target.value)}
        value={Array.isArray(condition.value) ? String(condition.value[0] ?? "") : condition.value}
      />
    </Field>
  )
}

function Provenance({ condition }: { readonly condition: DraftConditionState }) {
  return (
    <Collapsible className="flex min-w-0 flex-col gap-2">
      <CollapsibleTrigger
        render={<Button className="w-fit justify-start px-0" size="sm" variant="link" />}
      >
        查看原始模型值与来源证据
        <ChevronDownIcon aria-hidden="true" data-icon="inline-end" data-slot="chevron" />
      </CollapsibleTrigger>
      <CollapsibleContent className="flex flex-col gap-2 text-sm text-muted-foreground">
        {condition.modelSnapshot ? (
          <p className="m-0 break-words">
            模型原值：{formatConditionValue(condition.modelSnapshot.value)}，
            {condition.modelSnapshot.description}
          </p>
        ) : (
          <p className="m-0">成员新增条件，没有模型证据。</p>
        )}
        <EvidenceList evidence={condition.evidence} />
      </CollapsibleContent>
    </Collapsible>
  )
}

function UnsupportedSection() {
  const { actions, meta, state } = useRequirementDraftEditor()
  const count = state.unsupportedConditions.length
  const hasErrors = state.unsupportedConditions.some((item) => meta.errors[item.localId])
  const [expanded, setExpanded] = useState(false)
  const open = hasErrors || expanded

  return (
    <section aria-labelledby="draft-unsupported-heading" className="flex min-w-0 flex-col gap-4">
      {count === 0 ? (
        <>
          <div className="min-w-0">
            <FormSectionTitle id="draft-unsupported-heading">未支持条件</FormSectionTitle>
            <FormSectionDescription>
              保留给成员知情，不参与匹配，也不阻止后续确认。
            </FormSectionDescription>
          </div>
          <Empty>
            <EmptyHeader>
              <EmptyTitle>暂无未支持条件</EmptyTitle>
              <EmptyDescription>
                模型未能映射的条件会出现在这里，供成员知情，不参与匹配。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </>
      ) : (
        <Collapsible
          className="flex min-w-0 flex-col gap-3"
          onOpenChange={(next) => {
            if (hasErrors) return
            setExpanded(next)
          }}
          open={open}
        >
          <div className="flex min-w-0 flex-col gap-2">
            <div className="min-w-0">
              <FormSectionTitle id="draft-unsupported-heading">
                未支持条件 · {count.toLocaleString("zh-CN")} 条 · 不参与匹配
              </FormSectionTitle>
              <FormSectionDescription>
                保留给成员知情，不参与匹配，也不阻止后续确认。
                {hasErrors ? " 存在校验错误，已自动展开。" : null}
              </FormSectionDescription>
            </div>
            <CollapsibleTrigger
              disabled={hasErrors}
              render={<Button className="w-fit" size="sm" type="button" variant="outline" />}
            >
              {open ? "收起未支持条件" : "展开未支持条件"}
              <ChevronDownIcon aria-hidden="true" data-icon="inline-end" data-slot="chevron" />
            </CollapsibleTrigger>
          </div>
          <CollapsibleContent className="flex min-w-0 flex-col gap-3">
            {state.unsupportedConditions.map((item) => (
              <DataRegion key={item.localId}>
                <DataRegionContent className="flex flex-col gap-3 px-5 py-4">
                  <Field data-invalid={meta.errors[item.localId] ? true : undefined}>
                    <FieldLabel htmlFor={`draft-field-${item.localId}`}>
                      未支持 · {truncateLabel(item.description || "条件说明")}
                    </FieldLabel>
                    <Textarea
                      aria-invalid={meta.errors[item.localId] ? true : undefined}
                      autoComplete="off"
                      disabled={!meta.canEdit}
                      id={`draft-field-${item.localId}`}
                      name={`unsupported-description-${item.localId}`}
                      onChange={(event) =>
                        actions.updateUnsupported(item.localId, event.target.value)
                      }
                      value={item.description}
                    />
                    <FieldError>{meta.errors[item.localId]}</FieldError>
                    <EvidenceList evidence={item.evidence} />
                  </Field>
                </DataRegionContent>
                {meta.canEdit ? (
                  <DataRegionFooter>
                    <Button
                      onClick={() => actions.removeUnsupported(item.localId)}
                      size="sm"
                      type="button"
                      variant="ghost"
                    >
                      <Trash2Icon aria-hidden="true" data-icon="inline-start" />
                      删除
                    </Button>
                  </DataRegionFooter>
                ) : null}
              </DataRegion>
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}
    </section>
  )
}

function ConflictsSection() {
  const { actions, meta, state } = useRequirementDraftEditor()
  return (
    <section aria-labelledby="draft-conflicts-heading" className="flex min-w-0 flex-col gap-4">
      <div className="min-w-0">
        <FormSectionTitle id="draft-conflicts-heading">来源冲突</FormSectionTitle>
        <FormSectionDescription>
          解决冲突时必须填写处理说明；清除解决状态可重新打开。
        </FormSectionDescription>
      </div>
      {state.sourceConflicts.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>没有来源冲突</EmptyTitle>
            <EmptyDescription>
              多来源提取结果一致时，这里会保持为空。出现冲突后再逐条处理。
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        state.sourceConflicts.map((conflict) => (
          <DataRegion key={conflict.itemId}>
            <DataRegionContent className="flex flex-col gap-3 px-5 py-4">
              <p className="m-0 break-words font-medium">{conflict.description}</p>
              <EvidenceList evidence={conflict.evidence} />
              <Field orientation="horizontal">
                <Checkbox
                  checked={conflict.resolved}
                  disabled={!meta.canEdit}
                  id={`draft-conflict-${conflict.itemId}`}
                  name={`conflict-resolved-${conflict.itemId}`}
                  onCheckedChange={(checked) =>
                    actions.setConflictResolved(conflict.itemId, checked)
                  }
                />
                <FieldLabel htmlFor={`draft-conflict-${conflict.itemId}`}>标记为已解决</FieldLabel>
              </Field>
              <Field data-invalid={meta.errors[conflict.itemId] ? true : undefined}>
                <FieldLabel htmlFor={`draft-field-${conflict.itemId}`}>处理说明</FieldLabel>
                <Textarea
                  aria-invalid={meta.errors[conflict.itemId] ? true : undefined}
                  autoComplete="off"
                  disabled={!meta.canEdit || !conflict.resolved}
                  id={`draft-field-${conflict.itemId}`}
                  maxLength={2000}
                  name={`conflict-note-${conflict.itemId}`}
                  onChange={(event) => actions.setConflictNote(conflict.itemId, event.target.value)}
                  value={conflict.resolutionNote}
                />
                <FieldError>{meta.errors[conflict.itemId]}</FieldError>
              </Field>
            </DataRegionContent>
          </DataRegion>
        ))
      )}
    </section>
  )
}

function EditorActions() {
  const { actions, meta } = useRequirementDraftEditor()
  const busy =
    meta.pending || meta.abandoning || meta.confirming || meta.upgrading || meta.resolving
  return (
    <DataRegion aria-live="polite" ref={meta.feedbackRef} tabIndex={-1}>
      <DataRegionContent>
        {meta.feedback.kind === "ok" ? (
          <Alert>
            <AlertTitle>操作完成</AlertTitle>
            <AlertDescription>{meta.feedback.message}</AlertDescription>
          </Alert>
        ) : null}
        {meta.feedback.kind === "revisionConflict" ? (
          <Alert>
            <AlertTitle>已加载最新修订</AlertTitle>
            <AlertDescription>{meta.feedback.message}</AlertDescription>
          </Alert>
        ) : null}
        {meta.feedback.kind === "error" ? (
          <Alert>
            <AlertTitle>无法完成操作</AlertTitle>
            <AlertDescription>{meta.feedback.message}</AlertDescription>
          </Alert>
        ) : null}
        {Object.keys(meta.errors).length > 0 ? (
          <Alert>
            <AlertTitle>请检查草稿</AlertTitle>
            <AlertDescription>至少一个字段需要修正，焦点已移到首个错误。</AlertDescription>
          </Alert>
        ) : null}
        {meta.canEdit && meta.confirmBlockedReason !== null ? (
          <Alert>
            <AlertTitle>尚不能确认版本</AlertTitle>
            <AlertDescription>{meta.confirmBlockedReason}</AlertDescription>
          </Alert>
        ) : null}
      </DataRegionContent>
      {meta.canEdit ? (
        <DataRegionFooter className="flex flex-wrap justify-between gap-3">
          <AlertDialog>
            <AlertDialogTrigger render={<Button disabled={busy} type="button" variant="ghost" />}>
              放弃草稿
            </AlertDialogTrigger>
            <AlertDialogContent size="sm">
              <AlertDialogHeader>
                <AlertDialogTitle>放弃当前职位需求草稿？</AlertDialogTitle>
                <AlertDialogDescription>
                  草稿会进入终态，当前职位需求版本不会改变。 该操作保留历史草稿，但不能继续编辑。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={meta.abandoning}>继续编辑</AlertDialogCancel>
                <AlertDialogAction
                  onClick={actions.abandon}
                  pending={meta.abandoning}
                  type="button"
                  variant="destructive"
                >
                  {meta.abandoning ? "正在放弃…" : "确认放弃草稿"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={busy || !meta.dirty}
              pending={meta.pending}
              type="submit"
              variant="outline"
            >
              {meta.pending ? "正在保存…" : "保存草稿"}
            </Button>
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button disabled={busy || meta.confirmBlockedReason !== null} type="button" />
                }
              >
                确认版本
              </AlertDialogTrigger>
              <AlertDialogContent size="sm">
                <AlertDialogHeader>
                  <AlertDialogTitle>确认当前职位需求草稿？</AlertDialogTitle>
                  <AlertDialogDescription>
                    将创建不可变职位需求版本并切换为当前版本，历史匹配仍引用旧版本。
                    确认后此草稿会结束，后续修改需新建草稿或复制版本。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={meta.confirming}>继续编辑</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={actions.confirm}
                    pending={meta.confirming}
                    type="button"
                  >
                    {meta.confirming ? "正在确认…" : "确认版本"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </DataRegionFooter>
      ) : null}
    </DataRegion>
  )
}

function EvidenceList({ evidence }: { readonly evidence: readonly RequirementEvidence[] }) {
  if (evidence.length === 0) return null
  return (
    <Collapsible className="mt-2 flex min-w-0 flex-col gap-2">
      <CollapsibleTrigger
        render={<Button className="h-auto w-fit justify-start px-0" size="sm" variant="link" />}
      >
        来源证据 · {evidence.length.toLocaleString("zh-CN")}
        {evidence[0] ? ` · ${truncateLabel(evidence[0].quote, 32)}` : null}
        <ChevronDownIcon aria-hidden="true" data-icon="inline-end" data-slot="chevron" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {evidence.map((item) => (
            <li
              className="break-words text-sm text-muted-foreground"
              key={`${item.source_id}:${item.start_offset}:${item.end_offset}`}
            >
              <span className="font-mono text-xs" translate="no">
                {item.source_id} [{item.start_offset}, {item.end_offset})
              </span>
              ：“{item.quote}”
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}

function defaultValue(
  field: string,
  operator: string,
  identityValues: readonly string[],
): ConditionValue {
  if (numericFields.has(field)) return operator === "between" ? [0, 0] : 0
  if (field === "chinese_identity")
    return operator === "in" ? [identityValues[0] ?? "国内华人"] : (identityValues[0] ?? "国内华人")
  return operator === "in" ? [""] : ""
}

function valueForOperator(
  value: ConditionValue,
  field: string,
  operator: string,
  identityValues: readonly string[],
): ConditionValue {
  if (operator === "between") {
    const first = Array.isArray(value) ? (value[0] ?? 0) : value
    return [first, first]
  }
  if (operator === "in") return Array.isArray(value) ? value : [value]
  if (Array.isArray(value)) return value[0] ?? defaultValue(field, operator, identityValues)
  return value
}

function validateEditor(state: DraftEditorState, draft: RequirementDraft): Record<string, string> {
  const errors: Record<string, string> = {}
  if (!state.researchTopicQuery.trim()) {
    errors["research_topic_query"] = "研究主题查询不能为空。"
  }
  for (const item of [...state.hardConditions, ...state.preferenceConditions]) {
    if (!item.description.trim()) {
      errors[item.localId] = "条件说明不能为空。"
      continue
    }
    if (!(draft.field_catalog[item.field] ?? []).includes(item.operator)) {
      errors[item.localId] = "字段与操作符不兼容。"
      continue
    }
    const value = normalizeSubmittedValue(item)
    if (numericFields.has(item.field)) {
      const values = Array.isArray(value) ? value : [value]
      if (values.some((part) => typeof part !== "number" || !Number.isFinite(part) || part < 0)) {
        errors[item.localId] = "请输入不小于 0 的数值。"
      } else if (item.operator === "between" && Number(values[0]) > Number(values[1])) {
        errors[item.localId] = "区间下限不能大于上限。"
      }
    } else if (Array.isArray(value) ? value.length === 0 : !String(value).trim()) {
      errors[item.localId] = "条件值不能为空。"
    }
  }
  for (const item of state.unsupportedConditions) {
    if (!item.description.trim()) errors[item.localId] = "未支持条件说明不能为空。"
  }
  for (const conflict of state.sourceConflicts) {
    if (conflict.resolved && !conflict.resolutionNote.trim()) {
      errors[conflict.itemId] = "标记已解决时必须填写处理说明。"
    }
  }
  return errors
}

function formatConditionValue(value: unknown): string {
  return Array.isArray(value) ? value.join("、") : String(value)
}

export const RequirementDraftEditor = {
  Actions: EditorActions,
  Conditions: ConditionsSection,
  Conflicts: ConflictsSection,
  Frame: EditorFrame,
  Header: EditorHeader,
  PendingUpgrades: PendingUpgradeSection,
  Provider: RequirementDraftEditorProvider,
  ResearchTopic: ResearchTopicSection,
  Unsupported: UnsupportedSection,
}

export function JobRequirementDraftEditor({
  canManage,
  draft,
  jobId,
  onDirtyChange,
}: {
  readonly canManage: boolean
  readonly draft: RequirementDraft
  readonly jobId: string
  readonly onDirtyChange?: (dirty: boolean) => void
}) {
  return (
    <RequirementDraftEditor.Provider
      canManage={canManage}
      draft={draft}
      jobId={jobId}
      {...(onDirtyChange === undefined ? {} : { onDirtyChange })}
    >
      <RequirementDraftEditor.Frame>
        <RequirementDraftEditor.Header />
        <RequirementDraftEditor.PendingUpgrades />
        <RequirementDraftEditor.ResearchTopic />
        <RequirementDraftEditor.Conditions section="hard_conditions" title="硬条件" />
        <RequirementDraftEditor.Conditions section="preference_conditions" title="偏好条件" />
        <RequirementDraftEditor.Unsupported />
        <RequirementDraftEditor.Conflicts />
        <RequirementDraftEditor.Actions />
      </RequirementDraftEditor.Frame>
    </RequirementDraftEditor.Provider>
  )
}
