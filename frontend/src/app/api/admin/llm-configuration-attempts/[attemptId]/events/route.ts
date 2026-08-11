import { cookies } from "next/headers"
import { z } from "zod"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { databaseUuidSchema } from "@/lib/llm-configuration-contract"

const apiUrlSchema = z.url()

export const dynamic = "force-dynamic"

export async function GET(
  request: Request,
  context: { readonly params: Promise<{ readonly attemptId: string }> },
): Promise<Response> {
  const { attemptId } = await context.params
  if (!databaseUuidSchema.safeParse(attemptId).success) {
    return Response.json({ detail: "invalid_attempt_id" }, { status: 400 })
  }
  const session = (await cookies()).get(SESSION_COOKIE_NAME)?.value
  if (!session) return Response.json({ detail: "not_authenticated" }, { status: 401 })

  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  const headers = new Headers({ cookie: `${SESSION_COOKIE_NAME}=${session}` })
  const lastEventId = request.headers.get("Last-Event-ID")
  if (lastEventId !== null) headers.set("Last-Event-ID", lastEventId)

  const upstream = await fetch(
    new URL(`/admin/llm-configuration-attempts/${attemptId}/events`, baseUrl),
    { cache: "no-store", headers, signal: request.signal },
  )
  return new Response(upstream.body, {
    headers: {
      "Cache-Control": "no-cache, no-transform",
      "Content-Type": upstream.headers.get("Content-Type") ?? "text/event-stream",
      "X-Accel-Buffering": "no",
    },
    status: upstream.status,
  })
}
