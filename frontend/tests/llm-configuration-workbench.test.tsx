import { render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { LlmConfigurationWorkbench } from "@/components/admin/llm-configuration-workbench"
import type { LlmAttemptStatus, LlmWorkspace } from "@/lib/llm-configuration-contract"

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }))
vi.mock("@/app/actions/llm-configuration", () => ({
  cancelLlmConfigurationAction: vi.fn(),
  copyLlmConfigurationAction: vi.fn(),
  submitLlmConfigurationAction: vi.fn(),
}))

class FakeEventSource {
  static instances: FakeEventSource[] = []
  readonly listeners = new Map<string, EventListener>()

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: EventListener): void {
    this.listeners.set(type, listener)
  }

  close(): void {}
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal("EventSource", FakeEventSource)
})

const current = {
  created_at: "2026-08-11T08:00:00+00:00",
  created_by: null,
  id: "00000000-0000-0000-0000-000000000110",
  input_character_limit: 100_000,
  max_output_tokens: 8192,
  model: "x-ai/grok-4.5",
  privacy_routing: { data_collection: "deny", require_parameters: true, zdr: true },
  prompt_version_id: "job-requirement-prompt-v1",
  provider: "openrouter",
  request_timeout_seconds: 180,
  requirement_schema_version_id: "job-requirement-schema-v1",
  source: "migration_bootstrap",
  source_version_id: null,
  temperature: 0,
  version_number: 1,
} as const

function workspace(status: LlmAttemptStatus | null): LlmWorkspace {
  return {
    active_attempt:
      status === null
        ? null
        : {
            candidate: {
              max_output_tokens: 8192,
              model: current.model,
              prompt_version_id: current.prompt_version_id,
              request_timeout_seconds: 180,
              temperature: 0,
            },
            created_at: "2026-08-11T08:01:00+00:00",
            created_by: null,
            error_code: status === "failed" ? "model_unavailable" : null,
            expected_current_version_id: current.id,
            external_call_count: status === "queued" ? 0 : 1,
            id: "00000000-0000-0000-0000-000000000220",
            next_attempt_at: status === "retry_scheduled" ? "2026-08-11T08:05:00+00:00" : null,
            source_version_id: null,
            status,
            structured_invalid_count: 0,
            updated_at: "2026-08-11T08:02:00+00:00",
          },
    current,
    history: [current],
    prompt_versions: [
      {
        compatible_schema_version_id: "job-requirement-schema-v1",
        id: current.prompt_version_id,
        sha256: "a".repeat(64),
      },
    ],
    schema_versions: [],
  }
}

test("renders current configuration, candidate boundaries and immutable history", () => {
  render(<LlmConfigurationWorkbench workspace={workspace(null)} />)

  expect(screen.getAllByText("x-ai/grok-4.5").length).toBeGreaterThan(0)
  expect(screen.getByLabelText("最大输出 tokens")).toHaveAttribute("min", "1024")
  expect(screen.getByLabelText("最大输出 tokens")).toHaveAttribute("max", "16384")
  expect(screen.getByLabelText("请求超时（秒）")).toHaveAttribute("min", "30")
  expect(screen.getByText("版本不可原地修改；恢复会生成新的版本。")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "提交并探测" })).toBeEnabled()
})

test.each([
  ["queued", "等待执行"],
  ["running", "正在探测"],
  ["retry_scheduled", "等待重试"],
  ["cancel_requested", "正在取消"],
  ["succeeded", "已启用"],
  ["failed", "探测失败"],
  ["conflicted", "配置冲突"],
  ["cancelled", "已取消"],
] as const)("renders the persisted %s state as %s", (status, label) => {
  render(<LlmConfigurationWorkbench workspace={workspace(status)} />)

  expect(screen.getByText(label)).toBeInTheDocument()
  if (status === "queued") {
    expect(screen.getByRole("button", { name: "已有变更正在执行" })).toBeDisabled()
    expect(FakeEventSource.instances[0]?.url).toContain("/events")
  }
  if (status === "failed") expect(screen.getByText(/模型当前不可用/)).toBeInTheDocument()
})
