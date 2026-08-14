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
  "requirement_draft_replacement_conflict",
  "requirement_draft_not_found",
  "requirement_draft_revision_conflict",
  "requirement_draft_locked",
  "requirement_draft_not_editable",
  "requirement_draft_invalid",
  "research_topic_query_empty",
  "source_conflicts_unresolved",
  "requirement_version_not_found",
  "requirement_editable_draft_exists",
  "requirement_version_required",
  "requirement_configuration_not_ready",
  "idempotency_conflict",
  "requirement_creation_rate_limited",
  "requirement_task_not_found",
  "requirement_task_terminal",
  "requirement_schema_upgrade_unavailable",
  "requirement_schema_upgrade_not_found",
  "requirement_schema_upgrade_resolution_invalid",
  "schema_upgrade_lossy_unresolved",
  "requirement_input_purged",
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

export const requirementModelResultSchema = z
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

const editableMetadataShape = {
  item_id: uuidSchema,
  origin: z.enum(["model", "user_added"]),
  model_snapshot: executableConditionSchema.nullable(),
  last_modified_by: uuidSchema.nullable(),
  last_modified_at: dateTimeSchema.nullable(),
}

export const editableExecutableConditionSchema = z.union([
  numericThresholdSchema.extend(editableMetadataShape),
  numericBetweenSchema.extend(editableMetadataShape),
  chineseIdentityEqSchema.extend(editableMetadataShape),
  chineseIdentityInSchema.extend(editableMetadataShape),
  countryEqSchema.extend(editableMetadataShape),
  countryInSchema.extend(editableMetadataShape),
  affiliationSchema.extend(editableMetadataShape),
])

export const editableUnsupportedConditionSchema = z
  .object({
    item_id: uuidSchema,
    origin: z.enum(["model", "user_added"]),
    description: descriptionSchema,
    evidence: z.array(requirementEvidenceSchema).max(20),
    model_snapshot: z
      .object({ description: descriptionSchema, evidence: evidenceListSchema })
      .strict()
      .nullable(),
    last_modified_by: uuidSchema.nullable(),
    last_modified_at: dateTimeSchema.nullable(),
  })
  .strict()

export const editableSourceConflictSchema = z
  .object({
    item_id: uuidSchema,
    description: descriptionSchema,
    evidence: z.array(requirementEvidenceSchema).min(2).max(20),
    model_snapshot: z
      .object({
        description: descriptionSchema,
        evidence: z.array(requirementEvidenceSchema).min(2).max(20),
      })
      .strict(),
    resolution: z
      .object({
        note: descriptionSchema,
        resolved_by: uuidSchema,
        resolved_at: dateTimeSchema,
      })
      .strict()
      .nullable(),
  })
  .strict()

const removedFactSchema = z
  .object({
    item_id: uuidSchema,
    kind: z.enum(["hard_condition", "preference_condition", "unsupported_condition"]),
    origin: z.enum(["model", "user_added"]),
    model_snapshot: z
      .union([
        executableConditionSchema,
        z.object({ description: descriptionSchema, evidence: evidenceListSchema }).strict(),
      ])
      .nullable(),
    removed_snapshot: z.union([
      editableExecutableConditionSchema,
      editableUnsupportedConditionSchema,
    ]),
    removed_by: uuidSchema,
    removed_at: dateTimeSchema,
  })
  .strict()

export const requirementResultSchema = z
  .object({
    hard_conditions: z.array(editableExecutableConditionSchema).max(100),
    preference_conditions: z.array(editableExecutableConditionSchema).max(100),
    research_topic_query: z
      .object({
        value: z.string().min(1).max(4000),
        model_value: z.string().min(1).max(4000),
        last_modified_by: uuidSchema.nullable(),
        last_modified_at: dateTimeSchema.nullable(),
      })
      .strict(),
    unsupported_conditions: z.array(editableUnsupportedConditionSchema).max(100),
    source_conflicts: z.array(editableSourceConflictSchema).max(50),
    removed_facts: z.array(removedFactSchema).max(500),
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
  "requirement_draft_replacement_conflict",
  "job_archived",
  "requirement_input_purged",
])

export const requirementTaskSchema = z
  .object({
    id: uuidSchema,
    status: requirementTaskStatusSchema,
    error_code: requirementTaskErrorCodeSchema.nullable(),
    input_snapshot_id: uuidSchema,
    configuration_version_id: uuidSchema,
    replaces_draft_id: uuidSchema.nullable(),
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

const upgradeItemKindSchema = z.enum(["hard_condition", "preference_condition"])

export const pendingUpgradeItemSchema = z
  .object({
    item_id: uuidSchema,
    kind: upgradeItemKindSchema,
    snapshot: editableExecutableConditionSchema,
  })
  .strict()

export const requirementDraftSchema = z
  .object({
    id: uuidSchema,
    task_id: uuidSchema.nullable(),
    input_snapshot_id: uuidSchema.nullable(),
    source_version_id: uuidSchema.nullable(),
    requirement_schema_version_id: z.string(),
    status: z.enum(["editable", "confirmed", "replaced", "abandoned"]),
    revision: z.number().int().positive(),
    result: requirementResultSchema,
    updated_by: uuidSchema.nullable(),
    status_changed_at: dateTimeSchema,
    read_only_reason: z
      .enum(["job_archived", "replacement_in_progress", "draft_not_editable"])
      .nullable(),
    field_catalog: z.record(z.string(), z.array(z.string())),
    chinese_identity_values: z.array(chineseIdentitySchema).length(3),
    pending_upgrade_items: z.array(pendingUpgradeItemSchema).max(100),
    created_at: dateTimeSchema,
    updated_at: dateTimeSchema,
  })
  .strict()

export const requirementVersionSummarySchema = z
  .object({
    id: uuidSchema,
    version_number: z.number().int().positive(),
    requirement_schema_version_id: z.string(),
    draft_id: uuidSchema,
    source_version_id: uuidSchema.nullable(),
    confirmed_by: uuidSchema.nullable(),
    confirmed_at: dateTimeSchema,
    created_at: dateTimeSchema,
    is_current: z.boolean(),
  })
  .strict()

export const requirementVersionSchema = requirementVersionSummarySchema
  .extend({
    result: requirementResultSchema,
    input_snapshot_id: uuidSchema.nullable(),
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

const schemaUpgradeItemMappingSchema = z
  .object({
    item_id: uuidSchema,
    kind: upgradeItemKindSchema,
    mapping: z.string().min(1),
    lossless: z.boolean(),
  })
  .strict()

const schemaUpgradeLossyResolutionSchema = z
  .object({
    item_id: uuidSchema,
    kind: upgradeItemKindSchema,
    snapshot: editableExecutableConditionSchema,
    resolution: z
      .object({
        choice: z.enum(["drop", "downgrade_unsupported"]),
        resolved_by: uuidSchema,
        resolved_at: dateTimeSchema,
      })
      .strict()
      .nullable(),
  })
  .strict()

export const schemaUpgradeRecordSchema = z
  .object({
    id: uuidSchema,
    draft_id: uuidSchema,
    from_schema_version_id: z.string(),
    to_schema_version_id: z.string(),
    converter_version: z.string(),
    item_mappings: z.array(schemaUpgradeItemMappingSchema).max(200),
    lossy_resolutions: z.array(schemaUpgradeLossyResolutionSchema).max(200),
    actor_user_id: uuidSchema.nullable(),
    created_at: dateTimeSchema,
  })
  .strict()

export const schemaUpgradeResponseSchema = z
  .object({
    draft: requirementDraftSchema,
    upgrade: schemaUpgradeRecordSchema,
  })
  .strict()

export const schemaUpgradeResolutionInputSchema = z
  .object({
    item_id: uuidSchema,
    resolution: z.enum(["drop", "downgrade_unsupported"]),
  })
  .strict()

export const upgradeRequirementDraftSchemaInputSchema = z
  .object({ jobId: uuidSchema, draftId: uuidSchema, expectedRevision: z.number().int().positive() })
  .strict()

export const resolveSchemaUpgradeLossyItemsInputSchema = z
  .object({
    jobId: uuidSchema,
    draftId: uuidSchema,
    expectedRevision: z.number().int().positive(),
    resolutions: z.array(schemaUpgradeResolutionInputSchema).min(1).max(100),
  })
  .strict()

export const historyDraftSchema = z
  .object({
    id: uuidSchema,
    task_id: uuidSchema.nullable(),
    input_snapshot_id: uuidSchema.nullable(),
    source_version_id: uuidSchema.nullable(),
    requirement_schema_version_id: z.string(),
    status: z.enum(["editable", "confirmed", "replaced", "abandoned"]),
    revision: z.number().int().positive(),
    created_by: uuidSchema.nullable(),
    updated_by: uuidSchema.nullable(),
    status_changed_at: dateTimeSchema,
    created_at: dateTimeSchema,
    updated_at: dateTimeSchema,
  })
  .strict()

export const historySourceSchema = z
  .object({
    snapshot_id: uuidSchema,
    source_id: z.string().min(1).max(128),
    source_kind: z.enum(["job-description", "job-material"]),
    material_id: uuidSchema.nullable(),
    position: z.number().int().nonnegative(),
    original_sha256: z.string().length(64),
    sent_sha256: z.string().length(64),
    unicode_characters: z.number().int().nonnegative(),
    edited_by: uuidSchema.nullable(),
    edited_at: dateTimeSchema,
    body_purged_at: dateTimeSchema.nullable(),
  })
  .strict()

export const historyEventSchema = z
  .object({
    id: uuidSchema,
    actor_user_id: uuidSchema.nullable(),
    action: z.string().min(1),
    target_type: z.string().min(1),
    target_id: z.string().min(1),
    result: z.enum(["success", "failure"]),
    detail: z.string(),
    created_at: dateTimeSchema,
  })
  .strict()

export const requirementHistorySchema = z
  .object({
    tasks: z.array(requirementTaskSchema),
    drafts: z.array(historyDraftSchema),
    versions: z.array(requirementVersionSummarySchema),
    schema_upgrades: z.array(schemaUpgradeRecordSchema),
    sources: z.array(historySourceSchema),
    change_events: z.array(historyEventSchema),
  })
  .strict()

export const requirementWorkspaceSchema = z
  .object({
    configuration_ready: z.boolean(),
    input_character_limit: z.literal(100_000),
    sources: z.array(requirementSourceSchema),
    task: requirementTaskSchema.nullable(),
    draft: requirementDraftSchema.nullable(),
    current_version: requirementVersionSchema.nullable(),
    versions: z.array(requirementVersionSummarySchema),
    legacy_requirement_exempt: z.boolean(),
    matching_blocked: z.boolean(),
  })
  .strict()

export const confirmRequirementResponseSchema = z
  .object({
    version: requirementVersionSchema,
    draft: requirementDraftSchema,
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

const editableConditionSubmissionSchema = z
  .object({
    item_id: uuidSchema.nullable(),
    field: z.string().min(1).max(100),
    operator: z.string().min(1).max(50),
    value: z.unknown(),
    description: descriptionSchema,
  })
  .strict()

export const requirementDraftSubmissionSchema = z
  .object({
    hard_conditions: z.array(editableConditionSubmissionSchema).max(100),
    preference_conditions: z.array(editableConditionSubmissionSchema).max(100),
    research_topic_query: z.string().max(4000),
    unsupported_conditions: z
      .array(z.object({ item_id: uuidSchema.nullable(), description: descriptionSchema }).strict())
      .max(100),
    source_conflicts: z
      .array(
        z.object({ item_id: uuidSchema, resolution_note: descriptionSchema.nullable() }).strict(),
      )
      .max(50),
  })
  .strict()

export const updateRequirementDraftInputSchema = z
  .object({
    jobId: uuidSchema,
    draftId: uuidSchema,
    expectedRevision: z.number().int().positive(),
    result: requirementDraftSubmissionSchema,
  })
  .strict()

export const abandonRequirementDraftInputSchema = z
  .object({ jobId: uuidSchema, draftId: uuidSchema, expectedRevision: z.number().int().positive() })
  .strict()

export const confirmRequirementDraftInputSchema = z
  .object({ jobId: uuidSchema, draftId: uuidSchema, expectedRevision: z.number().int().positive() })
  .strict()

export const copyCurrentRequirementVersionInputSchema = z.object({ jobId: uuidSchema }).strict()

export const requirementDraftRevisionConflictSchema = z
  .object({
    detail: z.literal("requirement_draft_revision_conflict"),
    draft: requirementDraftSchema,
  })
  .strict()

export type ExecutableCondition = z.infer<typeof executableConditionSchema>
export type EditableExecutableCondition = z.infer<typeof editableExecutableConditionSchema>
export type EditableSourceConflict = z.infer<typeof editableSourceConflictSchema>
export type EditableUnsupportedCondition = z.infer<typeof editableUnsupportedConditionSchema>
export type HistoryDraft = z.infer<typeof historyDraftSchema>
export type HistoryEvent = z.infer<typeof historyEventSchema>
export type HistorySource = z.infer<typeof historySourceSchema>
export type PendingUpgradeItem = z.infer<typeof pendingUpgradeItemSchema>
export type RequirementDraft = z.infer<typeof requirementDraftSchema>
export type RequirementDraftSubmission = z.infer<typeof requirementDraftSubmissionSchema>
export type RequirementErrorDetail = z.infer<typeof requirementErrorSchema>["detail"]
export type RequirementEvidence = z.infer<typeof requirementEvidenceSchema>
export type RequirementHistory = z.infer<typeof requirementHistorySchema>
export type RequirementSource = z.infer<typeof requirementSourceSchema>
export type RequirementTask = z.infer<typeof requirementTaskSchema>
export type RequirementTaskEvent = z.infer<typeof requirementTaskEventSchema>
export type RequirementTaskStatus = z.infer<typeof requirementTaskStatusSchema>
export type RequirementVersion = z.infer<typeof requirementVersionSchema>
export type RequirementVersionSummary = z.infer<typeof requirementVersionSummarySchema>
export type RequirementWorkspace = z.infer<typeof requirementWorkspaceSchema>
export type SchemaUpgradeRecord = z.infer<typeof schemaUpgradeRecordSchema>
export type SchemaUpgradeResolutionInput = z.infer<typeof schemaUpgradeResolutionInputSchema>
export type SchemaUpgradeResponse = z.infer<typeof schemaUpgradeResponseSchema>
export type ConfirmRequirementResponse = z.infer<typeof confirmRequirementResponseSchema>
