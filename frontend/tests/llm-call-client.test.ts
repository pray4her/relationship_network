import { expect, test } from "vitest"

import {
  type LlmCallTransport,
  type LlmCallTransportResponse,
  loadLlmCallDetail,
  loadLlmCalls,
  revealLlmRawResponse,
  toLlmCallSearchParams,
} from "@/lib/llm-call-client"

const callId = "00000000-0000-0000-0000-000000000111"
const attemptId = "00000000-0000-0000-0000-000000000222"

class FixedTransport implements LlmCallTransport {
  constructor(private readonly response: LlmCallTransportResponse) {}

  detail(): Promise<LlmCallTransportResponse> {
    return Promise.resolve(this.response)
  }

  list(): Promise<LlmCallTransportResponse> {
    return Promise.resolve(this.response)
  }

  rawResponse(): Promise<LlmCallTransportResponse> {
    return Promise.resolve(this.response)
  }
}

const summary = {
  call_type: "config_probe",
  created_at: "2026-08-11T08:00:00+00:00",
  id: callId,
  job_requirement_parsing_task_id: null,
  metadata_status: "available",
  model: "x-ai/grok-4.5",
  outcome: "succeeded",
  platform_attempt_id: attemptId,
  raw_response_available: true,
  request_number: 1,
  scope: "platform",
  tenant_id: null,
} as const

test("maps every diagnostics filter to its stable URL key", () => {
  expect(
    toLlmCallSearchParams({
      callType: "config_probe",
      createdFrom: "2026-08-01T00:00:00.000Z",
      createdTo: "2026-08-11T23:59:59.999Z",
      cursor: "opaque cursor",
      metadataStatus: "retry_scheduled",
      outcome: "outcome_unknown",
      platformAttemptId: attemptId,
      scope: "platform",
      tenantId: callId,
    }).toString(),
  ).toBe(
    `scope=platform&call_type=config_probe&outcome=outcome_unknown&metadata_status=retry_scheduled&tenant_id=${callId}&platform_attempt_id=${attemptId}&created_from=2026-08-01T00%3A00%3A00.000Z&created_to=2026-08-11T23%3A59%3A59.999Z&cursor=opaque+cursor`,
  )
})

test("parses list and detail events without accepting encrypted storage fields", async () => {
  await expect(
    loadLlmCalls(
      new FixedTransport({ body: { calls: [summary], next_cursor: null }, status: 200 }),
      "session",
      {},
    ),
  ).resolves.toMatchObject({ kind: "ok", page: { calls: [summary] } })

  const detail = {
    call: {
      call_type: "config_probe",
      configuration_version_id: null,
      correlation_call_id: null,
      created_at: summary.created_at,
      id: callId,
      input_length: 2,
      input_sha256: "a".repeat(64),
      input_snapshot_id: null,
      input_sources_summary: { kind: "fixed_probe" },
      job_requirement_parsing_task_id: null,
      model: summary.model,
      parameters: { temperature: 0 },
      platform_attempt_id: attemptId,
      prompt_sha256: "b".repeat(64),
      prompt_version_id: "prompt-v1",
      request_hash: "c".repeat(64),
      request_number: 1,
      requirement_schema_sha256: "d".repeat(64),
      requirement_schema_version_id: "schema-v1",
      scope: "platform",
      scope_key: "platform",
      tenant_id: null,
    },
    metadata_events: [
      {
        actual_model: summary.model,
        actual_provider: "OpenAI",
        completion_tokens: 1,
        cost: 0.01,
        created_at: "2026-08-11T08:00:02+00:00",
        error_category: "",
        generation_id: "generation-1",
        next_retry_at: null,
        prompt_tokens: 1,
        sequence_number: 1,
        source: "response_body",
        status: "available",
        total_tokens: 2,
      },
    ],
    outcomes: [
      {
        actual_model: summary.model,
        actual_provider: "OpenAI",
        category: "ok",
        created_at: "2026-08-11T08:00:01+00:00",
        duration_ms: 120,
        http_status: 200,
        outcome: "succeeded",
        provider_request_id: "generation-1",
        sequence_number: 1,
      },
    ],
    raw_response_available: true,
    raw_response_expires_at: "2026-11-09T08:00:00+00:00",
  }
  await expect(
    loadLlmCallDetail(new FixedTransport({ body: detail, status: 200 }), "session", callId),
  ).resolves.toMatchObject({ detail, kind: "ok" })

  await expect(
    loadLlmCallDetail(
      new FixedTransport({
        body: { ...detail, ciphertext: "must-not-cross-contract" },
        status: 200,
      }),
      "session",
      callId,
    ),
  ).resolves.toEqual({ kind: "unreachable" })
})

test("maps raw response expiry and historical key failures to independent states", async () => {
  await expect(
    revealLlmRawResponse(
      new FixedTransport({ body: { detail: "llm_raw_response_not_found" }, status: 404 }),
      "session",
      callId,
    ),
  ).resolves.toEqual({ kind: "notFound" })
  await expect(
    revealLlmRawResponse(
      new FixedTransport({
        body: { detail: "llm_raw_response_key_unavailable" },
        status: 409,
      }),
      "session",
      callId,
    ),
  ).resolves.toEqual({ kind: "keyUnavailable" })
})
