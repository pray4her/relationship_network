import { z } from "zod"

export const searchErrorDetails = [
  "invalid_utterance",
  "search_idempotency_fingerprint_conflict",
  "search_creation_rate_limited",
  "search_in_progress",
  "search_quota_exceeded",
  "search_run_not_found",
  "invalid_sort",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
  "subscription_read_only",
] as const

export const searchErrorSchema = z.object({ detail: z.enum(searchErrorDetails) }).readonly()

export type SearchErrorDetail = z.infer<typeof searchErrorSchema>["detail"]

const searchHardConditionValueSchema = z.union([
  z.number(),
  z.string(),
  z.array(z.union([z.number(), z.string()])),
])

export const searchHardConditionSchema = z
  .object({
    field: z.string(),
    operator: z.string(),
    value: searchHardConditionValueSchema,
    description: z.string(),
  })
  .readonly()

export const searchUnsupportedConditionSchema = z.object({ description: z.string() }).readonly()

export const searchInterpretationSchema = z
  .object({
    hard_conditions: z.array(searchHardConditionSchema),
    research_topic_query: z.string(),
    unsupported_conditions: z.array(searchUnsupportedConditionSchema),
  })
  .readonly()

export const searchRunStatusSchema = z.enum(["in_progress", "succeeded", "failed"])

export const searchRunFailureReasonSchema = z.enum([
  "interpretation_invalid",
  "interpretation_error",
  "search_base_error",
  "search_base_timeout",
  "quota_exceeded",
])

export const searchRunViewSchema = z
  .object({
    id: z.string(),
    status: searchRunStatusSchema,
    failure_reason: searchRunFailureReasonSchema.nullable(),
    utterance: z.string(),
    utterance_length: z.number().int().nonnegative(),
    idempotency_key: z.string(),
    llm_configuration_version_id: z.string(),
    search_contract_version: z.string(),
    data_version: z.string().nullable(),
    request_id: z.string().nullable(),
    has_research_topic: z.boolean(),
    search_interpretation: searchInterpretationSchema.nullable(),
    created_at: z.string(),
  })
  .readonly()

export const searchHitSnapshotSchema = z
  .object({
    id: z.string(),
    local_talent_id: z.string(),
    canonical_person_id: z.string(),
    display_name: z.string(),
    current_affiliation: z.string(),
    country: z.string(),
    chinese_identity: z.enum(["国内华人", "海外华人", "外国人"]),
    h_index: z.number().int().nonnegative(),
    total_citations: z.number().int().nonnegative(),
    qs_top200_rank: z.number().int().nonnegative().nullable(),
    world_top500_rank: z.number().int().nonnegative().nullable(),
    has_contact: z.boolean().nullable(),
    data_version: z.string(),
    hit_publications: z.array(
      z
        .object({
          publication_id: z.string(),
          title: z.string(),
          year: z.number().int().nonnegative(),
          venue: z.string(),
          snippet: z.string().nullable(),
        })
        .readonly(),
    ),
    semantic_score: z.number().nullable(),
    sort_position: z.number().int().nonnegative(),
  })
  .readonly()

export const searchRunListSchema = z
  .object({
    runs: z.array(searchRunViewSchema),
    next_cursor: z.string().nullable(),
  })
  .readonly()

export const searchRunDetailSchema = z
  .object({
    run: searchRunViewSchema,
    hits: z.array(searchHitSnapshotSchema),
    next_cursor: z.string().nullable(),
    total: z.number().int().nonnegative(),
    sorted_by: z.string(),
    left_relevance_order: z.boolean(),
  })
  .readonly()

export type SearchRunView = z.infer<typeof searchRunViewSchema>
export type SearchHitSnapshot = z.infer<typeof searchHitSnapshotSchema>
export type SearchRunList = z.infer<typeof searchRunListSchema>
export type SearchRunDetail = z.infer<typeof searchRunDetailSchema>
export type SearchInterpretation = z.infer<typeof searchInterpretationSchema>
export type SearchRunStatus = z.infer<typeof searchRunStatusSchema>
export type SearchRunFailureReason = z.infer<typeof searchRunFailureReasonSchema>
