import { z } from "zod"

import { databaseUuidSchema } from "./llm-configuration-contract"

export const llmCallScopeSchema = z.enum(["platform", "tenant"])
export const llmCallTypeSchema = z.enum(["config_probe", "job_requirement_parsing"])
export const llmCallOutcomeSchema = z.enum([
  "succeeded",
  "failed",
  "outcome_unknown",
  "late_response",
])
export const llmCallMetadataStatusSchema = z.enum(["available", "retry_scheduled", "unavailable"])

export const llmCallSummarySchema = z
  .object({
    call_type: llmCallTypeSchema,
    created_at: z.iso.datetime({ offset: true }),
    id: databaseUuidSchema,
    job_requirement_parsing_task_id: databaseUuidSchema.nullable(),
    metadata_status: llmCallMetadataStatusSchema.nullable(),
    model: z.string(),
    outcome: llmCallOutcomeSchema.nullable(),
    platform_attempt_id: databaseUuidSchema.nullable(),
    raw_response_available: z.boolean(),
    request_number: z.number().int().positive(),
    scope: llmCallScopeSchema,
    tenant_id: databaseUuidSchema.nullable(),
  })
  .strict()

export const llmCallListSchema = z
  .object({
    calls: z.array(llmCallSummarySchema),
    next_cursor: z.string().nullable(),
  })
  .strict()

export const llmCallCoreSchema = z
  .object({
    call_type: llmCallTypeSchema,
    configuration_version_id: databaseUuidSchema.nullable(),
    correlation_call_id: databaseUuidSchema.nullable(),
    created_at: z.iso.datetime({ offset: true }),
    id: databaseUuidSchema,
    input_length: z.number().int().nonnegative(),
    input_sha256: z.string().length(64),
    input_snapshot_id: databaseUuidSchema.nullable(),
    input_sources_summary: z.record(z.string(), z.unknown()),
    job_requirement_parsing_task_id: databaseUuidSchema.nullable(),
    model: z.string(),
    parameters: z.record(z.string(), z.unknown()),
    platform_attempt_id: databaseUuidSchema.nullable(),
    prompt_sha256: z.string().length(64),
    prompt_version_id: z.string(),
    request_hash: z.string().length(64),
    request_number: z.number().int().positive(),
    requirement_schema_sha256: z.string().length(64),
    requirement_schema_version_id: z.string(),
    scope: llmCallScopeSchema,
    scope_key: z.string(),
    tenant_id: databaseUuidSchema.nullable(),
  })
  .strict()

export const llmCallOutcomeEventSchema = z
  .object({
    actual_model: z.string().nullable(),
    actual_provider: z.string().nullable(),
    category: z.string(),
    created_at: z.iso.datetime({ offset: true }),
    duration_ms: z.number().int().nonnegative().nullable(),
    http_status: z.number().int().nullable(),
    outcome: llmCallOutcomeSchema,
    provider_request_id: z.string().nullable(),
    sequence_number: z.number().int().positive(),
  })
  .strict()

export const llmCallMetadataEventSchema = z
  .object({
    actual_model: z.string().nullable(),
    actual_provider: z.string().nullable(),
    completion_tokens: z.number().int().nonnegative().nullable(),
    cost: z.number().nonnegative().nullable(),
    created_at: z.iso.datetime({ offset: true }),
    error_category: z.string(),
    generation_id: z.string().nullable(),
    next_retry_at: z.iso.datetime({ offset: true }).nullable(),
    prompt_tokens: z.number().int().nonnegative().nullable(),
    sequence_number: z.number().int().positive(),
    source: z.string(),
    status: llmCallMetadataStatusSchema,
    total_tokens: z.number().int().nonnegative().nullable(),
  })
  .strict()

export const llmCallDetailSchema = z
  .object({
    call: llmCallCoreSchema,
    metadata_events: z.array(llmCallMetadataEventSchema),
    outcomes: z.array(llmCallOutcomeEventSchema),
    raw_response_available: z.boolean(),
    raw_response_expires_at: z.iso.datetime({ offset: true }).nullable(),
  })
  .strict()

export const llmRawResponseSchema = z
  .object({
    body: z.string(),
    content_type: z.string().nullable(),
    created_at: z.iso.datetime({ offset: true }),
    encoding: z.enum(["utf-8", "base64"]),
    expires_at: z.iso.datetime({ offset: true }),
    http_status: z.number().int().nullable(),
    response_sequence: z.number().int().positive(),
  })
  .strict()

export const llmCallErrorSchema = z.object({ detail: z.string() }).strict()

export type LlmCallDetail = z.infer<typeof llmCallDetailSchema>
export type LlmCallList = z.infer<typeof llmCallListSchema>
export type LlmCallMetadataStatus = z.infer<typeof llmCallMetadataStatusSchema>
export type LlmCallOutcome = z.infer<typeof llmCallOutcomeSchema>
export type LlmCallScope = z.infer<typeof llmCallScopeSchema>
export type LlmCallType = z.infer<typeof llmCallTypeSchema>
export type LlmRawResponse = z.infer<typeof llmRawResponseSchema>
