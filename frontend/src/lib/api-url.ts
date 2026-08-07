import { z } from "zod"

const apiPublicUrlSchema = z.url()

export function apiPublicBaseUrl(): string {
  return apiPublicUrlSchema.parse(process.env["API_PUBLIC_URL"] ?? "http://localhost:8000")
}
