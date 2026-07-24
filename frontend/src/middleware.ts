import { type NextRequest, NextResponse } from "next/server"

import {
  createAuthTransport,
  loadAuthSession,
  SESSION_COOKIE_NAME,
  sessionCookieOptions,
} from "@/lib/auth-client"

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const response = NextResponse.next()
  const session = request.cookies.get(SESSION_COOKIE_NAME)
  if (!session?.value) {
    return response
  }

  try {
    const auth = await loadAuthSession(createAuthTransport(), session.value)
    if (auth.kind === "authenticated" && auth.renewedSession) {
      response.cookies.set(
        SESSION_COOKIE_NAME,
        auth.renewedSession.value,
        sessionCookieOptions(auth.renewedSession),
      )
    }
  } catch {
    // An unreachable API must never block page rendering.
  }

  return response
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
