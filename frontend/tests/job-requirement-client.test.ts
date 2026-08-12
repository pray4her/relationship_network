import { expect, test } from "vitest"

import {
  abandonRequirementDraft,
  createRequirementTask,
  loadRequirementWorkspace,
  type RequirementTransport,
  type RequirementTransportResponse,
  updateRequirementDraft,
} from "@/lib/job-requirement-client"

const jobId = "00000000-0000-4000-8000-000000000011"
const taskId = "00000000-0000-4000-8000-000000000022"
const snapshotId = "00000000-0000-4000-8000-000000000033"
const configurationId = "00000000-0000-4000-8000-000000000044"

const task = {
  id: taskId,
  status: "queued",
  error_code: null,
  input_snapshot_id: snapshotId,
  configuration_version_id: configurationId,
  replaces_draft_id: null,
  external_call_count: 0,
  structured_invalid_count: 0,
  created_by: null,
  created_at: "2026-08-11T08:00:00+00:00",
  started_at: null,
  completed_at: null,
  next_attempt_at: null,
  updated_at: "2026-08-11T08:00:00+00:00",
} as const

const workspace = {
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
  ],
  task: null,
  draft: null,
  current_version: null,
  versions: [],
  legacy_requirement_exempt: false,
  matching_blocked: false,
} as const

class FixedRequirementTransport implements RequirementTransport {
  constructor(private readonly response: RequirementTransportResponse) {}

  load(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  createTask(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  cancelTask(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  updateDraft(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  abandonDraft(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  confirmDraft(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  copyCurrentVersion(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }
}

test("strictly parses the requirement workspace", async () => {
  const result = await loadRequirementWorkspace(
    new FixedRequirementTransport({ body: workspace, status: 200 }),
    "session",
    jobId,
  )
  expect(result).toEqual({ kind: "ok", workspace })
})

test("rejects response drift instead of exposing unvalidated workspace data", async () => {
  const result = await loadRequirementWorkspace(
    new FixedRequirementTransport({ body: { ...workspace, unexpected: true }, status: 200 }),
    "session",
    jobId,
  )
  expect(result).toEqual({ kind: "unreachable" })
})

test("maps stable business and access failures without provider details", async () => {
  const conflict = await createRequirementTask(
    new FixedRequirementTransport({
      body: { detail: "requirement_input_too_large" },
      status: 422,
    }),
    "session",
    jobId,
    "idempotency-key",
    [{ source_id: "job-description", corrected_text: "职位描述" }],
  )
  const readOnly = await createRequirementTask(
    new FixedRequirementTransport({ body: { detail: "subscription_read_only" }, status: 403 }),
    "session",
    jobId,
    "idempotency-key",
    [{ source_id: "job-description", corrected_text: "职位描述" }],
  )

  expect(conflict).toEqual({ kind: "businessError", detail: "requirement_input_too_large" })
  expect(readOnly).toEqual({ kind: "readOnly" })
})

test("parses an accepted queued task", async () => {
  const result = await createRequirementTask(
    new FixedRequirementTransport({ body: task, status: 202 }),
    "session",
    jobId,
    "idempotency-key",
    [{ source_id: "job-description", corrected_text: "职位描述" }],
  )
  expect(result).toEqual({ kind: "ok", task })
})

test("returns the latest draft on an optimistic revision conflict", async () => {
  const latest = {
    id: "00000000-0000-4000-8000-000000000055",
    task_id: taskId,
    input_snapshot_id: snapshotId,
    source_version_id: null,
    requirement_schema_version_id: "job-requirement-schema-v2",
    status: "editable",
    revision: 2,
    result: {
      hard_conditions: [],
      preference_conditions: [],
      research_topic_query: {
        value: "人工智能",
        model_value: "人工智能",
        last_modified_by: null,
        last_modified_at: null,
      },
      unsupported_conditions: [],
      source_conflicts: [],
      removed_facts: [],
    },
    updated_by: null,
    status_changed_at: "2026-08-11T08:00:00+00:00",
    read_only_reason: null,
    field_catalog: { h_index: ["gte", "lte"] },
    chinese_identity_values: ["国内华人", "海外华人", "外国人"],
    created_at: "2026-08-11T08:00:00+00:00",
    updated_at: "2026-08-11T08:01:00+00:00",
  } as const
  const result = await updateRequirementDraft(
    new FixedRequirementTransport({
      body: { detail: "requirement_draft_revision_conflict", draft: latest },
      status: 409,
    }),
    "session",
    jobId,
    latest.id,
    1,
    {
      hard_conditions: [],
      preference_conditions: [],
      research_topic_query: "人工智能",
      unsupported_conditions: [],
      source_conflicts: [],
    },
  )

  expect(result).toEqual({ kind: "revisionConflict", draft: latest })
})

test("maps abandon read-only failures", async () => {
  const result = await abandonRequirementDraft(
    new FixedRequirementTransport({ body: { detail: "subscription_read_only" }, status: 403 }),
    "session",
    jobId,
    "00000000-0000-4000-8000-000000000055",
    1,
  )
  expect(result).toEqual({ kind: "readOnly" })
})
