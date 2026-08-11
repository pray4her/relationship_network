import { expect, test } from "vitest"

import {
  createRequirementTask,
  loadRequirementWorkspace,
  type RequirementTransport,
  type RequirementTransportResponse,
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
