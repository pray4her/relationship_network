import { expect, test } from "vitest"

import {
  cancelLlmAttempt,
  createLlmAttempt,
  type LlmConfigurationTransport,
  type LlmTransportResponse,
  loadLlmWorkspace,
} from "@/lib/llm-configuration-client"

const callBindings = {
  job_requirement_parsing: {
    prompt_version_id: "job-requirement-prompt-v1",
    request_timeout_seconds: 180,
  },
  search_interpretation: {
    prompt_version_id: "search-interpretation-prompt-v1",
    request_timeout_seconds: 15,
  },
} as const

const version = {
  call_bindings: callBindings,
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

const attempt = {
  candidate: {
    call_bindings: callBindings,
    max_output_tokens: 8192,
    model: "x-ai/grok-4.5",
    prompt_version_id: "job-requirement-prompt-v1",
    request_timeout_seconds: 180,
    temperature: 0,
  },
  created_at: "2026-08-11T08:01:00+00:00",
  created_by: null,
  error_code: null,
  expected_current_version_id: version.id,
  external_call_count: 0,
  id: "00000000-0000-0000-0000-000000000220",
  next_attempt_at: null,
  probe_progress: {},
  source_version_id: null,
  status: "queued",
  structured_invalid_count: 0,
  updated_at: "2026-08-11T08:01:00+00:00",
} as const

class FixedTransport implements LlmConfigurationTransport {
  constructor(private readonly response: LlmTransportResponse) {}

  cancel(): Promise<LlmTransportResponse> {
    return Promise.resolve(this.response)
  }

  copy(): Promise<LlmTransportResponse> {
    return Promise.resolve(this.response)
  }

  create(): Promise<LlmTransportResponse> {
    return Promise.resolve(this.response)
  }

  read(): Promise<LlmTransportResponse> {
    return Promise.resolve(this.response)
  }
}

test("parses the immutable LLM configuration workspace", async () => {
  const body = {
    active_attempt: null,
    current: version,
    history: [version],
    prompt_versions: [
      {
        call_type: "job_requirement_parsing",
        compatible_schema_version_id: "job-requirement-schema-v1",
        id: "job-requirement-prompt-v1",
        sha256: "a".repeat(64),
      },
    ],
    schema_versions: [
      {
        chinese_identity_values: ["国内华人", "海外华人", "外国人"],
        field_catalog: { h_index: ["gte", "lte", "between"] },
        id: "job-requirement-schema-v1",
        output_limits: { combined_conditions: 100 },
        schema_id: "urn:relationship-network:job-requirement-schema:v1",
        sha256: "b".repeat(64),
      },
    ],
  }

  await expect(
    loadLlmWorkspace(new FixedTransport({ body, status: 200 }), "session"),
  ).resolves.toEqual({
    kind: "ok",
    workspace: body,
  })
})

test("maps a successful create and idempotent cancel to attempt views", async () => {
  const transport = new FixedTransport({ body: attempt, status: 202 })

  await expect(
    createLlmAttempt(transport, "session", attempt.candidate, version.id),
  ).resolves.toEqual({
    attempt,
    kind: "ok",
  })
  await expect(cancelLlmAttempt(transport, "session", attempt.id)).resolves.toEqual({
    attempt,
    kind: "ok",
  })
})

test("accepts create responses whose candidate includes the frozen input_character_limit", async () => {
  // Backend _attempt_view setdefault("input_character_limit", 100_000) on candidate_snapshot.
  const body = {
    ...attempt,
    candidate: { ...attempt.candidate, input_character_limit: 100_000 as const },
  }

  await expect(
    createLlmAttempt(
      new FixedTransport({ body, status: 202 }),
      "session",
      attempt.candidate,
      version.id,
    ),
  ).resolves.toEqual({
    attempt: body,
    kind: "ok",
  })
})

test("preserves stable conflict details and the active attempt ID", async () => {
  await expect(
    createLlmAttempt(
      new FixedTransport({
        body: { attempt_id: attempt.id, detail: "config_change_in_progress" },
        status: 409,
      }),
      "session",
      attempt.candidate,
      version.id,
    ),
  ).resolves.toEqual({
    attemptId: attempt.id,
    detail: "config_change_in_progress",
    kind: "conflict",
  })
})

test("rejects success payloads with secret or unknown candidate fields", async () => {
  const poisoned = {
    active_attempt: { ...attempt, candidate: { ...attempt.candidate, api_key: "secret" } },
    current: version,
    history: [version],
    prompt_versions: [],
    schema_versions: [],
  }

  await expect(
    loadLlmWorkspace(new FixedTransport({ body: poisoned, status: 200 }), "session"),
  ).resolves.toEqual({ kind: "unreachable" })
})
