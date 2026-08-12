import { z } from "zod"

export const databaseUuidSchema = z
  .string()
  .regex(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i, "Invalid UUID")

export const llmAttemptStatusSchema = z.enum([
  "queued",
  "running",
  "retry_scheduled",
  "cancel_requested",
  "succeeded",
  "failed",
  "conflicted",
  "cancelled",
])

export const llmCandidateSchema = z
  .object({
    input_character_limit: z.literal(100_000).optional(),
    max_output_tokens: z.number().int().min(1024).max(16384),
    model: z.string().trim().min(1).max(200),
    prompt_version_id: z.string().trim().min(1).max(100),
    request_timeout_seconds: z.number().int().min(30).max(300),
    temperature: z.number().min(0).max(1),
  })
  .strict()

export const llmConfigurationVersionSchema = llmCandidateSchema.extend({
  created_at: z.iso.datetime({ offset: true }),
  created_by: databaseUuidSchema.nullable(),
  id: databaseUuidSchema,
  input_character_limit: z.literal(100_000),
  privacy_routing: z.record(z.string(), z.unknown()),
  provider: z.string(),
  requirement_schema_version_id: z.string(),
  source: z.string(),
  source_version_id: databaseUuidSchema.nullable(),
  version_number: z.number().int().positive(),
})

export const llmAttemptSchema = z.object({
  candidate: llmCandidateSchema,
  created_at: z.iso.datetime({ offset: true }),
  created_by: databaseUuidSchema.nullable(),
  error_code: z.string().nullable(),
  expected_current_version_id: databaseUuidSchema,
  external_call_count: z.number().int().min(0).max(3),
  id: databaseUuidSchema,
  next_attempt_at: z.iso.datetime({ offset: true }).nullable(),
  source_version_id: databaseUuidSchema.nullable(),
  status: llmAttemptStatusSchema,
  structured_invalid_count: z.number().int().min(0).max(2),
  updated_at: z.iso.datetime({ offset: true }),
})

export const llmPromptVersionSchema = z.object({
  compatible_schema_version_id: z.string(),
  id: z.string(),
  sha256: z.string().length(64),
})

export const llmSchemaSummarySchema = z.object({
  chinese_identity_values: z.array(z.string()),
  field_catalog: z.record(z.string(), z.unknown()),
  id: z.string(),
  output_limits: z.record(z.string(), z.number().int()),
  schema_id: z.string(),
  sha256: z.string().length(64),
})

export const llmWorkspaceSchema = z.object({
  active_attempt: llmAttemptSchema.nullable(),
  current: llmConfigurationVersionSchema,
  history: z.array(llmConfigurationVersionSchema),
  prompt_versions: z.array(llmPromptVersionSchema),
  schema_versions: z.array(llmSchemaSummarySchema),
})

export const llmErrorSchema = z.object({
  attempt_id: databaseUuidSchema.optional(),
  detail: z.string(),
})

export const llmAttemptEventDataSchema = z.object({
  attempt_id: databaseUuidSchema,
  created_at: z.iso.datetime({ offset: true }),
  payload: z.record(z.string(), z.unknown()),
  status: llmAttemptStatusSchema,
})

export type LlmAttempt = z.infer<typeof llmAttemptSchema>
export type LlmAttemptEventData = z.infer<typeof llmAttemptEventDataSchema>
export type LlmAttemptStatus = z.infer<typeof llmAttemptStatusSchema>
export type LlmCandidate = z.infer<typeof llmCandidateSchema>
export type LlmConfigurationVersion = z.infer<typeof llmConfigurationVersionSchema>
export type LlmWorkspace = z.infer<typeof llmWorkspaceSchema>
