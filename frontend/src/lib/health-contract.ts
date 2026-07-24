import { z } from "zod"

export const dependencyNames = ["postgres", "redis", "object_storage"] as const

export const healthResponseSchema = z
  .object({
    dependencies: z
      .array(
        z
          .object({
            name: z.enum(dependencyNames),
            status: z.enum(["ok", "unavailable"]),
          })
          .readonly(),
      )
      .readonly(),
    status: z.enum(["ok", "degraded"]),
  })
  .readonly()

export type HealthResponse = z.infer<typeof healthResponseSchema>

export type DashboardHealth =
  | { readonly kind: "ready"; readonly value: HealthResponse }
  | { readonly kind: "unreachable"; readonly reason: string }
