import { z } from "zod"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const paramsSchema = z.object({ id: z.string().uuid(), taskId: z.string().uuid() }).strict()
const apiUrlSchema = z.url()

export async function GET(
  request: Request,
  context: { readonly params: Promise<{ readonly id: string; readonly taskId: string }> },
): Promise<Response> {
  const params = paramsSchema.safeParse(await context.params)
  if (!params.success) {
    return Response.json({ detail: "requirement_task_not_found" }, { status: 404 })
  }
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  const upstreamUrl = new URL(
    `/jobs/${params.data.id}/requirement-parsing-tasks/${params.data.taskId}/events`,
    baseUrl,
  )
  const headers = new Headers({ Accept: "text/event-stream" })
  const cookie = request.headers.get("cookie")
  const lastEventId = request.headers.get("last-event-id")
  if (cookie !== null) headers.set("cookie", cookie)
  if (lastEventId !== null) headers.set("last-event-id", lastEventId)

  let upstream: Response
  try {
    upstream = await fetch(upstreamUrl, {
      cache: "no-store",
      headers,
      method: "GET",
      signal: request.signal,
    })
  } catch {
    return Response.json({ detail: "requirement_events_unavailable" }, { status: 503 })
  }

  return new Response(upstream.body, {
    headers: {
      "Cache-Control": "no-cache, no-store, no-transform",
      Connection: "keep-alive",
      "Content-Type": upstream.headers.get("content-type") ?? "text/event-stream; charset=utf-8",
      "X-Accel-Buffering": "no",
    },
    status: upstream.status,
    statusText: upstream.statusText,
  })
}
