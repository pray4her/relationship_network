import { expect, test } from "vitest"

import {
  abandonRequirementDraft,
  createRequirementTask,
  loadRequirementHistory,
  loadRequirementWorkspace,
  type RequirementTransport,
  type RequirementTransportResponse,
  resolveSchemaUpgradeLossyItems,
  updateRequirementDraft,
  upgradeRequirementDraftSchema,
} from "@/lib/job-requirement-client"
import { requirementHistorySchema } from "@/lib/job-requirement-contract"

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

  loadHistory(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  upgradeSchema(): Promise<RequirementTransportResponse> {
    return Promise.resolve(this.response)
  }

  resolveSchemaUpgrade(): Promise<RequirementTransportResponse> {
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
    pending_upgrade_items: [],
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

const draftId = "00000000-0000-4000-8000-000000000055"
const upgradeId = "00000000-0000-4000-8000-000000000066"
const lossyItemId = "00000000-0000-4000-8000-000000000077"

const lossySnapshot = {
  item_id: lossyItemId,
  origin: "model",
  field: "chinese_identity",
  operator: "eq",
  value: "海外华人",
  description: "限定海外华人",
  evidence: [{ source_id: "job-description", start_offset: 0, end_offset: 2, quote: "负责" }],
  model_snapshot: null,
  last_modified_by: null,
  last_modified_at: null,
} as const

const upgradedDraft = {
  id: draftId,
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
  field_catalog: { chinese_identity: ["eq", "in"] },
  chinese_identity_values: ["国内华人", "海外华人", "外国人"],
  pending_upgrade_items: [
    { item_id: lossyItemId, kind: "preference_condition", snapshot: lossySnapshot },
  ],
  created_at: "2026-08-11T08:00:00+00:00",
  updated_at: "2026-08-11T08:01:00+00:00",
} as const

const upgradeRecord = {
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
} as const

const history = {
  tasks: [task],
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
      version_number: 1,
      requirement_schema_version_id: "job-requirement-schema-v1",
      draft_id: draftId,
      source_version_id: null,
      confirmed_by: null,
      confirmed_at: "2026-08-11T08:01:00+00:00",
      created_at: "2026-08-11T08:01:00+00:00",
      is_current: true,
    },
  ],
  schema_upgrades: [upgradeRecord],
  sources: [
    {
      snapshot_id: snapshotId,
      source_id: "job-description",
      source_kind: "job-description",
      material_id: null,
      position: 0,
      original_sha256: "a".repeat(64),
      sent_sha256: "b".repeat(64),
      unicode_characters: 42,
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
} as const

test("strictly parses the requirement history response", async () => {
  const result = await loadRequirementHistory(
    new FixedRequirementTransport({ body: history, status: 200 }),
    "session",
    jobId,
  )
  expect(result).toEqual({ kind: "ok", history })
  expect(requirementHistorySchema.parse(history)).toEqual(history)
})

test("maps requirement history lookup failures", async () => {
  const missing = await loadRequirementHistory(
    new FixedRequirementTransport({ body: { detail: "job_not_found" }, status: 404 }),
    "session",
    jobId,
  )
  const drift = await loadRequirementHistory(
    new FixedRequirementTransport({ body: { ...history, unexpected: true }, status: 200 }),
    "session",
    jobId,
  )
  expect(missing).toEqual({ kind: "notFound" })
  expect(drift).toEqual({ kind: "unreachable" })
})

test("parses a draft with pending upgrade items after a schema upgrade", async () => {
  const result = await upgradeRequirementDraftSchema(
    new FixedRequirementTransport({
      body: { draft: upgradedDraft, upgrade: upgradeRecord },
      status: 200,
    }),
    "session",
    jobId,
    draftId,
    1,
  )
  expect(result).toEqual({ kind: "ok", draft: upgradedDraft, upgrade: upgradeRecord })
})

test("maps schema upgrade business errors and revision conflicts", async () => {
  const unavailable = await upgradeRequirementDraftSchema(
    new FixedRequirementTransport({
      body: { detail: "requirement_schema_upgrade_unavailable" },
      status: 409,
    }),
    "session",
    jobId,
    draftId,
    1,
  )
  expect(unavailable).toEqual({
    kind: "businessError",
    detail: "requirement_schema_upgrade_unavailable",
  })

  const conflict = await upgradeRequirementDraftSchema(
    new FixedRequirementTransport({
      body: { detail: "requirement_draft_revision_conflict", draft: upgradedDraft },
      status: 409,
    }),
    "session",
    jobId,
    draftId,
    1,
  )
  expect(conflict).toEqual({ kind: "revisionConflict", draft: upgradedDraft })
})

test("resolves lossy upgrade items and maps resolution errors", async () => {
  const resolvedDraft = { ...upgradedDraft, revision: 3, pending_upgrade_items: [] }
  const ok = await resolveSchemaUpgradeLossyItems(
    new FixedRequirementTransport({ body: resolvedDraft, status: 200 }),
    "session",
    jobId,
    draftId,
    upgradeId,
    2,
    [{ item_id: lossyItemId, resolution: "downgrade_unsupported" }],
  )
  expect(ok).toEqual({ kind: "ok", draft: resolvedDraft })

  const invalid = await resolveSchemaUpgradeLossyItems(
    new FixedRequirementTransport({
      body: { detail: "requirement_schema_upgrade_resolution_invalid" },
      status: 422,
    }),
    "session",
    jobId,
    draftId,
    upgradeId,
    2,
    [{ item_id: lossyItemId, resolution: "drop" }],
  )
  expect(invalid).toEqual({
    kind: "businessError",
    detail: "requirement_schema_upgrade_resolution_invalid",
  })

  const conflict = await resolveSchemaUpgradeLossyItems(
    new FixedRequirementTransport({
      body: { detail: "requirement_draft_revision_conflict", draft: upgradedDraft },
      status: 409,
    }),
    "session",
    jobId,
    draftId,
    upgradeId,
    2,
    [{ item_id: lossyItemId, resolution: "drop" }],
  )
  expect(conflict).toEqual({ kind: "revisionConflict", draft: upgradedDraft })
})
