import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { RequirementGenerator } from "@/components/jobs/requirement-generator"
import type { RequirementTask, RequirementWorkspace } from "@/lib/job-requirement-contract"

const mocks = vi.hoisted(() => ({ action: vi.fn(), cancelAction: vi.fn(), refresh: vi.fn() }))

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: mocks.refresh }) }))
vi.mock("@/app/actions/job-requirements", () => ({
  cancelRequirementTaskAction: mocks.cancelAction,
  generateRequirementDraftAction: mocks.action,
}))

const jobId = "00000000-0000-4000-8000-000000000011"
const materialId = "00000000-0000-4000-8000-000000000012"
const task: RequirementTask = {
  id: "00000000-0000-4000-8000-000000000022",
  status: "queued",
  error_code: null,
  input_snapshot_id: "00000000-0000-4000-8000-000000000033",
  configuration_version_id: "00000000-0000-4000-8000-000000000044",
  external_call_count: 0,
  structured_invalid_count: 0,
  created_by: null,
  created_at: "2026-08-11T08:00:00+00:00",
  started_at: null,
  completed_at: null,
  next_attempt_at: null,
  updated_at: "2026-08-11T08:00:00+00:00",
}

function workspace(overrides: Partial<RequirementWorkspace> = {}): RequirementWorkspace {
  return {
    configuration_ready: true,
    input_character_limit: 100_000,
    sources: [
      {
        source_id: "job-description",
        source_kind: "job-description",
        material_id: null,
        label: "职位描述",
        original_text: "负责人才检索",
        scan_status: "not_applicable",
        created_at: null,
      },
      {
        source_id: `job-material:${materialId}`,
        source_kind: "job-material",
        material_id: materialId,
        label: "材料：补充说明.txt",
        original_text: "",
        scan_status: "content_checked",
        created_at: "2026-08-11T08:01:00+00:00",
      },
    ],
    task: null,
    draft: null,
    ...overrides,
  }
}

function renderGenerator(value: RequirementWorkspace, canManage = true) {
  return render(
    <RequirementGenerator.Provider
      archived={false}
      canManage={canManage}
      jobId={jobId}
      workspace={value}
    >
      <RequirementGenerator.TaskStatus />
      <RequirementGenerator.DraftViewer />
      <RequirementGenerator.SourceEditors />
      <RequirementGenerator.Summary />
    </RequirementGenerator.Provider>,
  )
}

beforeEach(() => {
  mocks.action.mockReset()
  mocks.cancelAction.mockReset()
  mocks.refresh.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test("empty material becomes selectable only after a correction and counts Unicode code points", () => {
  renderGenerator(workspace())
  const checkboxes = screen.getAllByRole("checkbox")
  const corrections = screen.getAllByLabelText("修正文案")
  const materialCheckbox = checkboxes.at(1)
  const materialCorrection = corrections.at(1)
  if (!materialCheckbox || !materialCorrection) throw new Error("material editor is missing")

  expect(materialCheckbox).toHaveAttribute("aria-disabled", "true")
  fireEvent.change(materialCorrection, { target: { value: "😀e\u0301" } })
  expect(screen.getByText("2 字符")).toBeInTheDocument()
  expect(materialCheckbox).not.toHaveAttribute("aria-disabled")
  fireEvent.click(materialCheckbox)
  expect(screen.getByText(/已选择 1 个来源/)).toHaveTextContent("2 / 100,000 字符")
})

test("submits only selected corrected sources and restores queued task state", async () => {
  mocks.action.mockResolvedValue({ kind: "ok", task })
  renderGenerator(workspace())

  const descriptionCheckbox = screen.getAllByRole("checkbox").at(0)
  if (!descriptionCheckbox) throw new Error("description editor is missing")
  fireEvent.click(descriptionCheckbox)
  fireEvent.click(screen.getByRole("button", { name: "生成职位需求草稿" }))

  await waitFor(() =>
    expect(mocks.action).toHaveBeenCalledWith(jobId, expect.any(String), [
      { source_id: "job-description", corrected_text: "负责人才检索" },
    ]),
  )
  expect(await screen.findByText("排队中")).toBeInTheDocument()
  expect(mocks.refresh).toHaveBeenCalledOnce()
})

test("reuses the idempotency key for the same snapshot and rotates it after an edit", async () => {
  mocks.action.mockResolvedValue({ kind: "error", message: "网络超时，请重试。" })
  renderGenerator(workspace())

  const descriptionCheckbox = screen.getAllByRole("checkbox").at(0)
  const descriptionCorrection = screen.getAllByLabelText("修正文案").at(0)
  if (!descriptionCheckbox || !descriptionCorrection)
    throw new Error("description editor is missing")
  fireEvent.click(descriptionCheckbox)

  const submit = screen.getByRole("button", { name: "生成职位需求草稿" })
  fireEvent.click(submit)
  await waitFor(() => expect(mocks.action).toHaveBeenCalledTimes(1))
  await screen.findByText("网络超时，请重试。")
  await waitFor(() => expect(submit).toBeEnabled())
  const firstKey = mocks.action.mock.calls[0]?.[1]

  fireEvent.click(submit)
  await waitFor(() => expect(mocks.action).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(submit).toBeEnabled())
  expect(mocks.action.mock.calls[1]?.[1]).toBe(firstKey)

  fireEvent.change(descriptionCorrection, { target: { value: "负责全球人才检索" } })
  fireEvent.click(submit)
  await waitFor(() => expect(mocks.action).toHaveBeenCalledTimes(3))
  expect(mocks.action.mock.calls[2]?.[1]).not.toBe(firstKey)
})

test("applies a terminal SSE event, closes the stream, and refreshes persisted data", async () => {
  class FakeEventSource {
    static instances: FakeEventSource[] = []

    readonly listeners = new Map<string, EventListener>()
    readonly close = vi.fn()
    onerror: ((event: Event) => void) | null = null
    onopen: ((event: Event) => void) | null = null

    constructor(readonly url: string) {
      FakeEventSource.instances.push(this)
    }

    addEventListener(type: string, listener: EventListener) {
      this.listeners.set(type, listener)
    }
  }

  vi.stubGlobal("EventSource", FakeEventSource)
  renderGenerator(workspace({ task }))
  const source = FakeEventSource.instances.at(0)
  if (!source) throw new Error("EventSource was not opened")

  expect(source.url).toBe(`/jobs/${jobId}/requirement-parsing-tasks/${task.id}/events`)
  source.onopen?.(new Event("open"))
  expect(await screen.findByText("实时状态已连接")).toBeInTheDocument()

  const terminal = {
    sequence_number: 2,
    task_id: task.id,
    status: "cancelled",
    error_code: null,
    retryable: false,
    next_attempt_at: null,
    created_at: "2026-08-11T08:02:00+00:00",
  }
  source.listeners.get("cancelled")?.(
    new MessageEvent("cancelled", { data: JSON.stringify(terminal) }),
  )

  expect(await screen.findByText("已取消")).toBeInTheDocument()
  expect(source.close).toHaveBeenCalled()
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledOnce())
})

test("confirms cancellation before invoking the server action", async () => {
  mocks.cancelAction.mockResolvedValue({
    kind: "ok",
    task: { ...task, status: "cancelled", completed_at: "2026-08-11T08:02:00+00:00" },
  })
  renderGenerator(workspace({ task }))

  fireEvent.click(screen.getByRole("button", { name: "取消任务" }))
  expect(mocks.cancelAction).not.toHaveBeenCalled()
  fireEvent.click(await screen.findByRole("button", { name: "确认取消任务" }))

  await waitFor(() => expect(mocks.cancelAction).toHaveBeenCalledWith(jobId, task.id))
  expect(await screen.findByText("已取消")).toBeInTheDocument()
})

test("blocks submission when the normalized Unicode input exceeds the frozen limit", () => {
  renderGenerator(workspace())
  const materialCorrection = screen.getAllByLabelText("修正文案").at(1)
  const materialCheckbox = screen.getAllByRole("checkbox").at(1)
  if (!materialCorrection || !materialCheckbox) throw new Error("material editor is missing")

  fireEvent.change(materialCorrection, { target: { value: "😀".repeat(100_001) } })
  fireEvent.click(materialCheckbox)

  expect(screen.getByText("已超限")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "生成职位需求草稿" })).toBeDisabled()
})

test("read-only members can inspect sources but cannot edit or submit", () => {
  renderGenerator(workspace(), false)

  expect(screen.getAllByLabelText("修正文案").at(0)).toBeDisabled()
  expect(screen.queryByRole("button", { name: "生成职位需求草稿" })).not.toBeInTheDocument()
  expect(screen.getAllByDisplayValue("负责人才检索")).toHaveLength(2)
})

test("failed task explains the stable reason and refreshes from the database", () => {
  renderGenerator(
    workspace({
      task: {
        ...task,
        status: "failed",
        error_code: "requirement_output_invalid",
        completed_at: "2026-08-11T08:02:00+00:00",
      },
    }),
  )

  expect(screen.getByText(/未通过完整结构或来源证据校验/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "刷新状态" }))
  expect(mocks.refresh).toHaveBeenCalledOnce()
})

test("renders the complete validated draft in explicit groups", () => {
  renderGenerator(
    workspace({
      draft: {
        id: "00000000-0000-4000-8000-000000000055",
        task_id: task.id,
        input_snapshot_id: task.input_snapshot_id,
        requirement_schema_version_id: "job-requirement-schema-v2",
        status: "editable",
        revision: 1,
        result: {
          hard_conditions: [
            {
              field: "h_index",
              operator: "gte",
              value: 30,
              description: "H 指数至少 30",
              evidence: [
                { source_id: "job-description", start_offset: 0, end_offset: 2, quote: "负责" },
              ],
            },
          ],
          preference_conditions: [],
          research_topic_query: "人工智能 AND 医疗",
          unsupported_conditions: [
            {
              description: "要求有创业经验",
              evidence: [
                { source_id: "job-description", start_offset: 0, end_offset: 2, quote: "负责" },
              ],
            },
          ],
          source_conflicts: [],
        },
        created_at: "2026-08-11T08:03:00+00:00",
        updated_at: "2026-08-11T08:03:00+00:00",
      },
    }),
  )

  expect(screen.getByRole("heading", { name: "硬条件" })).toBeInTheDocument()
  expect(screen.getByText("H 指数至少 30")).toBeInTheDocument()
  expect(screen.getByRole("heading", { name: "研究主题查询" })).toBeInTheDocument()
  expect(screen.getByText("人工智能 AND 医疗")).toBeInTheDocument()
  expect(screen.getByRole("heading", { name: "未支持条件" })).toBeInTheDocument()
  expect(screen.getByText("要求有创业经验")).toBeInTheDocument()
})
