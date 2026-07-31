import { cookies } from "next/headers"

import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "./auth-client"

export type AdminGateFailure = "noSession" | "anonymous" | "unreachable" | "forbidden"

export type AdminGuardResult =
  | { readonly kind: "ok"; readonly session: string }
  | { readonly kind: AdminGateFailure }

export async function requireAdminView(): Promise<AdminGuardResult> {
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return { kind: "noSession" }
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind === "anonymous") {
    return { kind: "anonymous" }
  }
  if (auth.kind !== "authenticated") {
    return { kind: "unreachable" }
  }
  if (!auth.view.user.is_platform_admin) {
    return { kind: "forbidden" }
  }
  return { kind: "ok", session }
}
