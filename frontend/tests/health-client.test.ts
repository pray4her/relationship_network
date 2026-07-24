import { afterEach, expect, test, vi } from "vitest"

import {
  createReadinessTransport,
  HealthTransportError,
  loadDashboardHealth,
  type ReadinessTransport,
} from "../src/lib/health-client"

afterEach(() => {
  vi.unstubAllGlobals()
})

class FixedTransport implements ReadinessTransport {
  readonly #response: unknown

  constructor(response: unknown) {
    this.#response = response
  }

  async read(): Promise<unknown> {
    return this.#response
  }
}

class FailingTransport implements ReadinessTransport {
  async read(): Promise<unknown> {
    throw new HealthTransportError("connection failed")
  }
}

test("parses a valid API readiness response", async () => {
  // Given a transport returns the documented API response
  const transport = new FixedTransport({
    dependencies: [
      { name: "postgres", status: "ok" },
      { name: "redis", status: "ok" },
      { name: "object_storage", status: "ok" },
    ],
    status: "ok",
  })

  // When health data crosses the frontend boundary
  const result = await loadDashboardHealth(transport)

  // Then the page receives a parsed connected state
  expect(result.kind).toBe("ready")
})

test("returns a user-visible recovery state for transport failures", async () => {
  // Given the API transport cannot connect
  const transport = new FailingTransport()

  // When the page loads health data
  const result = await loadDashboardHealth(transport)

  // Then the failure is represented as a stable renderable state
  expect(result).toEqual({ kind: "unreachable", reason: "API 暂时无法连接" })
})

test("returns a user-visible recovery state for invalid API data", async () => {
  // Given the API returns a payload outside the documented schema
  const transport = new FixedTransport({ status: "unexpected" })

  // When health data crosses the frontend boundary
  const result = await loadDashboardHealth(transport)

  // Then invalid data is not trusted by the component tree
  expect(result).toEqual({ kind: "unreachable", reason: "API 返回了无法识别的状态" })
})

test("preserves a degraded readiness body returned with HTTP 503", async () => {
  // Given the API reports one unavailable dependency with its readiness contract
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            dependencies: [
              { name: "postgres", status: "ok" },
              { name: "redis", status: "unavailable" },
              { name: "object_storage", status: "ok" },
            ],
            status: "degraded",
          }),
          { headers: { "content-type": "application/json" }, status: 503 },
        ),
    ),
  )

  // When the real HTTP transport reads the degraded response
  const result = await loadDashboardHealth(createReadinessTransport())

  // Then dependency detail remains renderable instead of becoming unreachable
  expect(result).toEqual({
    kind: "ready",
    value: {
      dependencies: [
        { name: "postgres", status: "ok" },
        { name: "redis", status: "unavailable" },
        { name: "object_storage", status: "ok" },
      ],
      status: "degraded",
    },
  })
})

test("returns an invalid-response state for a non-JSON HTTP error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response("internal server error", {
          headers: { "content-type": "text/plain" },
          status: 500,
        }),
    ),
  )

  const result = await loadDashboardHealth(createReadinessTransport())

  expect(result).toEqual({ kind: "unreachable", reason: "API 返回了无法识别的状态" })
})
