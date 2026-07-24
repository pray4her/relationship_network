import ky, { TimeoutError } from "ky"
import { ZodError, z } from "zod"

import { type DashboardHealth, healthResponseSchema } from "./health-contract"

const apiUrlSchema = z.url()

export interface ReadinessTransport {
  read(): Promise<unknown>
}

export class HealthTransportError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "HealthTransportError"
  }
}

class KyReadinessTransport implements ReadinessTransport {
  readonly #endpoint: string

  constructor(endpoint: string) {
    this.#endpoint = endpoint
  }

  async read(): Promise<unknown> {
    try {
      return await ky
        .get(this.#endpoint, {
          cache: "no-store",
          retry: 0,
          throwHttpErrors: false,
          timeout: 10_000,
        })
        .json<unknown>()
    } catch (error) {
      if (error instanceof TimeoutError || error instanceof TypeError) {
        throw new HealthTransportError("readiness endpoint unavailable")
      }
      throw error
    }
  }
}

export function createReadinessTransport(): ReadinessTransport {
  const baseUrl = apiUrlSchema.parse(process.env["API_INTERNAL_URL"] ?? "http://localhost:8000")
  return new KyReadinessTransport(new URL("/health/ready", baseUrl).toString())
}

export async function loadDashboardHealth(transport: ReadinessTransport): Promise<DashboardHealth> {
  try {
    const rawHealth = await transport.read()
    return { kind: "ready", value: healthResponseSchema.parse(rawHealth) }
  } catch (error) {
    if (error instanceof HealthTransportError) {
      return { kind: "unreachable", reason: "API 暂时无法连接" }
    }
    if (error instanceof SyntaxError || error instanceof ZodError) {
      return { kind: "unreachable", reason: "API 返回了无法识别的状态" }
    }
    throw error
  }
}
