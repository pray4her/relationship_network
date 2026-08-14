import { z } from "zod"

export const talentsErrorDetails = [
  "talent_not_found",
  "permission_denied",
  "mfa_required",
  "not_authenticated",
  "no_active_membership",
] as const

export const talentsErrorSchema = z
  .object({
    detail: z.enum(talentsErrorDetails),
  })
  .readonly()

export const talentAvailabilitySchema = z.enum(["available", "temporarily_unavailable"])

export const talentViewSchema = z
  .object({
    id: z.string(),
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
    availability: talentAvailabilitySchema,
    last_synced_at: z.string(),
    historical_source_ids: z.array(z.string()),
  })
  .readonly()

export type TalentView = z.infer<typeof talentViewSchema>
export type TalentAvailability = z.infer<typeof talentAvailabilitySchema>
export type TalentsErrorDetail = z.infer<typeof talentsErrorSchema>["detail"]
