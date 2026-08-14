import { render, screen } from "@testing-library/react"
import { expect, test } from "vitest"

import { RequirementHistoryView } from "@/components/jobs/requirement-history"
import type { RequirementHistory } from "@/lib/job-requirement-contract"

const taskId = "00000000-0000-4000-8000-000000000022"
const snapshotId = "00000000-0000-4000-8000-000000000033"
const draftId = "00000000-0000-4000-8000-000000000055"
const upgradeId = "00000000-0000-4000-8000-000000000066"
const lossyItemId = "00000000-0000-4000-8000-000000000077"

const lossySnapshot = {
  item_id: lossyItemId,
  origin: "model" as const,
  field: "chinese_identity" as const,
  operator: "eq" as const,
  value: "海外华人" as const,
  description: "限定海外华人",
  evidence: [{ source_id: "job-description", start_offset: 0, end_offset: 2, quote: "负责" }],
  model_snapshot: null,
  last_modified_by: null,
  last_modified_at: null,
}

function history(overrides: Partial<RequirementHistory> = {}): RequirementHistory {
  return {
    tasks: [
      {
        id: taskId,
        status: "failed",
        error_code: "requirement_input_purged",
        input_snapshot_id: snapshotId,
        configuration_version_id: "00000000-0000-4000-8000-000000000044",
        replaces_draft_id: null,
        external_call_count: 1,
        structured_invalid_count: 0,
        created_by: null,
        created_at: "2026-08-11T08:00:00+00:00",
        started_at: "2026-08-11T08:00:10+00:00",
        completed_at: "2026-08-11T08:01:00+00:00",
        next_attempt_at: null,
        updated_at: "2026-08-11T08:01:00+00:00",
      },
    ],
    drafts: [
      {
        id: draftId,
        task_id: taskId,
        input_snapshot_id: snapshotId,
        source_version_id: null,
        requirement_schema_version_id: "job-requirement-schema-v2",
        status: "editable",
        revision: 2,
        created_by: null,
        updated_by: null,
        status_changed_at: "2026-08-11T08:00:00+00:00",
        created_at: "2026-08-11T08:00:00+00:00",
        updated_at: "2026-08-11T08:01:00+00:00",
      },
    ],
    versions: [
      {
        id: "00000000-0000-4000-8000-000000000099",
        version_number: 3,
        requirement_schema_version_id: "job-requirement-schema-v1",
        draft_id: draftId,
        source_version_id: null,
        confirmed_by: null,
        confirmed_at: "2026-08-11T08:01:00+00:00",
        created_at: "2026-08-11T08:01:00+00:00",
        is_current: true,
      },
    ],
    schema_upgrades: [
      {
        id: upgradeId,
        draft_id: draftId,
        from_schema_version_id: "job-requirement-schema-v1",
        to_schema_version_id: "job-requirement-schema-v2",
        converter_version: "v1-to-v2@1",
        item_mappings: [
          {
            item_id: "00000000-0000-4000-8000-000000000088",
            kind: "hard_condition",
            mapping: "copied",
            lossless: true,
          },
          {
            item_id: lossyItemId,
            kind: "preference_condition",
            mapping: "unconvertible_chinese_identity",
            lossless: false,
          },
        ],
        lossy_resolutions: [
          {
            item_id: lossyItemId,
            kind: "preference_condition",
            snapshot: lossySnapshot,
            resolution: null,
          },
        ],
        actor_user_id: null,
        created_at: "2026-08-11T08:02:00+00:00",
      },
    ],
    sources: [
      {
        snapshot_id: snapshotId,
        source_id: "job-description",
        source_kind: "job-description",
        material_id: null,
        position: 0,
        original_sha256: "a".repeat(64),
        sent_sha256: `${"b".repeat(12)}${"0".repeat(52)}`,
        unicode_characters: 42,
        edited_by: null,
        edited_at: "2026-08-11T08:00:00+00:00",
        body_purged_at: "2026-08-15T00:00:00+00:00",
      },
      {
        snapshot_id: "00000000-0000-4000-8000-000000000034",
        source_id: "job-material:00000000-0000-4000-8000-000000000012",
        source_kind: "job-material",
        material_id: "00000000-0000-4000-8000-000000000012",
        position: 1,
        original_sha256: "c".repeat(64),
        sent_sha256: "c".repeat(64),
        unicode_characters: 128,
        edited_by: null,
        edited_at: "2026-08-11T08:00:00+00:00",
        body_purged_at: null,
      },
    ],
    change_events: [
      {
        id: "00000000-0000-4000-8000-000000000111",
        actor_user_id: null,
        action: "job_requirement_draft.schema_upgrade",
        target_type: "job_requirement_draft",
        target_id: draftId,
        result: "success",
        detail: "resolved=1 revision=2",
        created_at: "2026-08-11T08:02:00+00:00",
      },
    ],
    ...overrides,
  }
}

test("renders every business layer with its facts", () => {
  render(<RequirementHistoryView history={history()} />)

  expect(screen.getByRole("heading", { name: "解析任务" })).toBeInTheDocument()
  expect(screen.getByText("生成失败")).toBeInTheDocument()
  expect(screen.getByText("requirement_input_purged")).toBeInTheDocument()

  expect(screen.getByRole("heading", { name: "草稿" })).toBeInTheDocument()
  expect(screen.getByText("编辑中")).toBeInTheDocument()
  expect(screen.getAllByText("job-requirement-schema-v2").length).toBeGreaterThan(0)

  expect(screen.getByRole("heading", { name: "版本" })).toBeInTheDocument()
  expect(screen.getByText("v3")).toBeInTheDocument()
  expect(screen.getByText("当前")).toBeInTheDocument()

  expect(screen.getByRole("heading", { name: "Schema 升级" })).toBeInTheDocument()
  expect(
    screen.getByText("job-requirement-schema-v1 → job-requirement-schema-v2"),
  ).toBeInTheDocument()
  expect(screen.getByText("v1-to-v2@1")).toBeInTheDocument()
  expect(screen.getByText(/无损 1 · 有损 1/)).toBeInTheDocument()
  expect(screen.getByText("1 项待解决")).toBeInTheDocument()

  expect(screen.getByRole("heading", { name: "来源快照" })).toBeInTheDocument()
  expect(screen.getByText("职位描述")).toBeInTheDocument()
  expect(screen.getByText("职位材料")).toBeInTheDocument()
  expect(screen.getByText(`${"b".repeat(12)}…`)).toBeInTheDocument()
  expect(screen.getByText("正文已清理")).toBeInTheDocument()
  expect(screen.getByText("正文保留")).toBeInTheDocument()

  expect(screen.getByRole("heading", { name: "变更记录" })).toBeInTheDocument()
  expect(screen.getByText("job_requirement_draft.schema_upgrade")).toBeInTheDocument()
  expect(screen.getByText("成功")).toBeInTheDocument()
  expect(screen.getByText("resolved=1 revision=2")).toBeInTheDocument()
})

test("shows empty notes when the job has no requirement history", () => {
  render(
    <RequirementHistoryView
      history={history({
        tasks: [],
        drafts: [],
        versions: [],
        schema_upgrades: [],
        sources: [],
        change_events: [],
      })}
    />,
  )

  expect(screen.getByText("尚无解析任务记录。")).toBeInTheDocument()
  expect(screen.getByText("尚无草稿记录。")).toBeInTheDocument()
  expect(screen.getByText("尚无确认的职位需求版本。")).toBeInTheDocument()
  expect(screen.getByText("尚无 Schema 升级记录。")).toBeInTheDocument()
  expect(screen.getByText("尚无来源快照记录。")).toBeInTheDocument()
  expect(screen.getByText("尚无变更记录。")).toBeInTheDocument()
})
