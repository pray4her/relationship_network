import { cookies } from "next/headers"

import { SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createLlmCallTransport, revealLlmRawResponse } from "@/lib/llm-call-client"
import { databaseUuidSchema } from "@/lib/llm-configuration-contract"

export const dynamic = "force-dynamic"

const noStoreHeaders = { "Cache-Control": "no-store" }

export async function POST(
  _request: Request,
  context: { readonly params: Promise<{ readonly callId: string }> },
): Promise<Response> {
  const { callId } = await context.params
  if (!databaseUuidSchema.safeParse(callId).success) {
    return Response.json({ detail: "invalid_call_id" }, { headers: noStoreHeaders, status: 400 })
  }
  const session = (await cookies()).get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return Response.json({ detail: "not_authenticated" }, { headers: noStoreHeaders, status: 401 })
  }

  const result = await revealLlmRawResponse(createLlmCallTransport(), session, callId)
  switch (result.kind) {
    case "ok":
      return Response.json(result.response, { headers: noStoreHeaders })
    case "anonymous":
      return Response.json(
        { detail: "not_authenticated" },
        { headers: noStoreHeaders, status: 401 },
      )
    case "forbidden":
      return Response.json({ detail: "forbidden" }, { headers: noStoreHeaders, status: 403 })
    case "mfaRequired":
      return Response.json({ detail: "mfa_required" }, { headers: noStoreHeaders, status: 403 })
    case "notFound":
      return Response.json(
        { detail: "llm_raw_response_not_found" },
        { headers: noStoreHeaders, status: 404 },
      )
    case "keyUnavailable":
      return Response.json(
        { detail: "llm_raw_response_key_unavailable" },
        { headers: noStoreHeaders, status: 409 },
      )
    case "unreachable":
      return Response.json(
        { detail: "llm_raw_response_unavailable" },
        { headers: noStoreHeaders, status: 502 },
      )
  }
}
