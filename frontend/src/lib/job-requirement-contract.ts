import { z } from "zod"

const uuidSchema = z.string().uuid()
const dateTimeSchema = z.iso.datetime({ offset: true })

export const requirementErrorDetails = [
  "job_not_found",
  "job_archived",
  "requirement_source_not_found",
  "requirement_material_unavailable",
  "requirement_input_empty",
  "requirement_material_correction_empty",
  "requirement_input_too_large",
  "requirement_task_exists",
  "requirement_draft_exists",
  "requirement_configuration_not_ready",
  "idempotency_conflict",
  "requirement_creation_rate_limited",
  "requirement_task_not_found",
  "requirement_task_terminal",
  "subscription_read_only",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const requirementErrorSchema = z.object({ detail: z.enum(requirementErrorDetails) }).strict()

export const requirementEvidenceSchema = z
  .object({
    source_id: z.string().min(1).max(128),
    start_offset: z.number().int().nonnegative(),
    end_offset: z.number().int().positive(),
    quote: z.string().min(1).max(2000),
  })
  .strict()

const evidenceListSchema = z.array(requirementEvidenceSchema).min(1).max(20)
const numericFieldSchema = z.enum([
  "qs_top200_rank",
  "world_top500_rank",
  "h_index",
  "total_citations",
])
const descriptionSchema = z.string().min(1).max(2000)

const numericThresholdSchema = z
  .object({
    field: numericFieldSchema,
    operator: z.enum(["gte", "lte"]),
    value: z.number().nonnegative(),
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()

const numericBetweenSchema = z
  .object({
    field: numericFieldSchema,
    operator: z.literal("between"),
    value: z.tuple([z.number().nonnegative(), z.number().nonnegative()]),
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()

const chineseIdentitySchema = z.enum(["国内华人", "海外华人", "外国人"])
const chineseIdentityEqSchema = z
  .object({
    field: z.literal("chinese_identity"),
    operator: z.literal("eq"),
    value: chineseIdentitySchema,
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()
const chineseIdentityInSchema = z
  .object({
    field: z.literal("chinese_identity"),
    operator: z.literal("in"),
    value: z.array(chineseIdentitySchema).min(1).max(3),
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()
const countryEqSchema = z
  .object({
    field: z.literal("country"),
    operator: z.literal("eq"),
    value: z.string().min(1).max(200),
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()
const countryInSchema = z
  .object({
    field: z.literal("country"),
    operator: z.literal("in"),
    value: z.array(z.string().min(1).max(200)).min(1).max(50),
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()
const affiliationSchema = z
  .object({
    field: z.literal("current_affiliation"),
    operator: z.enum(["match", "match_phrase"]),
    value: z.string().min(1).max(500),
    description: descriptionSchema,
    evidence: evidenceListSchema,
  })
  .strict()

export const executableConditionSchema = z.union([
  numericThresholdSchema,
  numericBetweenSchema,
  chineseIdentityEqSchema,
  chineseIdentityInSchema,
  countryEqSchema,
  countryInSchema,
  affiliationSchema,
])

export const requirementResultSchema = z
  .object({
    hard_conditions: z.array(executableConditionSchema).max(100),
    preference_conditions: z.array(executableConditionSchema).max(100),
    research_topic_query: z.string().min(1).max(4000),
    unsupported_conditions: z
      .array(z.object({ description: descriptionSchema, evidence: evidenceListSchema }).strict())
      .max(100),
    source_conflicts: z
      .array(
        z
          .object({
            description: descriptionSchema,
            evidence: z.array(requirementEvidenceSchema).min(2).max(20),
          })
          .strict(),
      )
      .max(50),
  })
  .strict()

export const requirementTaskStatusSchema = z.enum([
  "queued",
  "running",
  "retry_scheduled",
  "cancel_requested",
  "succeeded",
  "failed",
  "cancelled",
])

export const requirementTaskErrorCodeSchema = z.enum([
  "requirement_output_invalid",
  "requirement_generation_unavailable",
  "requirement_configuration_unavailable",
  "requirement_draft_exists",
  "job_archived",
])

export const requirementTaskSchema = z
  .object({
    id: uuidSchema,
    status: requirementTaskStatusSchema,
    error_code: requirementTaskErrorCodeSchema.nullable(),
    input_snapshot_id: uuidSchema,
    configuration_version_id: uuidSchema,
    external_call_count: z.number().int().min(0).max(3),
    structured_invalid_count: z.number().int().min(0).max(2),
    created_by: uuidSchema.nullable(),
    created_at: dateTimeSchema,
    started_at: dateTimeSchema.nullable(),
    completed_at: dateTimeSchema.nullable(),
    next_attempt_at: dateTimeSchema.nullable(),
    updated_at: dateTimeSchema,
  })
  .strict()

export const requirementTaskEventSchema = z
  .object({
    sequence_number: z.number().int().positive(),
    task_id: uuidSchema,
    status: requirementTaskStatusSchema,
    error_code: requirementTaskErrorCodeSchema.nullable(),
    retryable: z.boolean(),
    next_attempt_at: dateTimeSchema.nullable(),
    created_at: dateTimeSchema,
  })
  .strict()

export const requirementDraftSchema = z
  .object({
    id: uuidSchema,
    task_id: uuidSchema,
    input_snapshot_id: uuidSchema,
    requirement_schema_version_id: z.string(),
    status: z.enum(["editable", "confirmed", "replaced", "abandoned"]),
    revision: z.number().int().positive(),
    result: requirementResultSchema,
    created_at: dateTimeSchema,
    updated_at: dateTimeSchema,
  })
  .strict()

export const requirementSourceSchema = z
  .object({
    source_id: z.string().min(1).max(128),
    source_kind: z.enum(["job-description", "job-material"]),
    material_id: uuidSchema.nullable(),
    label: z.string().min(1),
    original_text: z.string(),
    scan_status: z.string(),
    created_at: dateTimeSchema.nullable(),
  })
  .strict()

export const requirementWorkspaceSchema = z
  .object({
    configuration_ready: z.boolean(),
    input_character_limit: z.literal(100_000),
    sources: z.array(requirementSourceSchema),
    task: requirementTaskSchema.nullable(),
    draft: requirementDraftSchema.nullable(),
  })
  .strict()

export const createRequirementTaskInputSchema = z
  .object({
    jobId: uuidSchema,
    idempotencyKey: z.string().min(1).max(128),
    sources: z
      .array(
        z
          .object({
            source_id: z.string().min(1).max(128),
            corrected_text: z.string(),
          })
          .strict(),
      )
      .min(1),
  })
  .strict()

export const cancelRequirementTaskInputSchema = z
  .object({ jobId: uuidSchema, taskId: uuidSchema })
  .strict()

export type ExecutableCondition = z.infer<typeof executableConditionSchema>
export type RequirementDraft = z.infer<typeof requirementDraftSchema>
export type RequirementErrorDetail = z.infer<typeof requirementErrorSchema>["detail"]
export type RequirementEvidence = z.infer<typeof requirementEvidenceSchema>
export type RequirementSource = z.infer<typeof requirementSourceSchema>
export type RequirementTask = z.infer<typeof requirementTaskSchema>
export type RequirementTaskEvent = z.infer<typeof requirementTaskEventSchema>
export type RequirementTaskStatus = z.infer<typeof requirementTaskStatusSchema>
export type RequirementWorkspace = z.infer<typeof requirementWorkspaceSchema>
