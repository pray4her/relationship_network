import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { LlmRawResponseDialog } from "@/components/admin/llm-raw-response-dialog"

const callId = "00000000-0000-0000-0000-000000000111"
const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal("fetch", fetchMock)
})

test("does not request the raw response before an explicit click", async () => {
  fetchMock.mockResolvedValue(
    Response.json({
      body: JSON.stringify({ answer: 42 }),
      content_type: "application/json",
      created_at: "2026-08-11T08:00:00+00:00",
      encoding: "utf-8",
      expires_at: "2026-11-09T08:00:00+00:00",
      http_status: 200,
      response_sequence: 1,
    }),
  )
  render(<LlmRawResponseDialog available callId={callId} />)

  expect(fetchMock).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "查看原始响应" }))

  expect(await screen.findByRole("dialog")).toBeInTheDocument()
  expect(await screen.findByText(/"answer": 42/)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(`/api/admin/llm-calls/${callId}/raw-response`, {
    cache: "no-store",
    method: "POST",
  })
})

test.each([
  [404, { detail: "llm_raw_response_not_found" }, "原始响应不存在或已超过 90 天保留期。"],
  [409, { detail: "llm_raw_response_key_unavailable" }, "历史密钥不可用，无法解密这条原始响应。"],
] as const)("renders the independent %s failure state", async (status, body, message) => {
  fetchMock.mockResolvedValue(Response.json(body, { status }))
  render(<LlmRawResponseDialog available callId={callId} />)

  fireEvent.click(screen.getByRole("button", { name: "查看原始响应" }))

  expect(await screen.findByText(message)).toBeInTheDocument()
})

test("disables disclosure when no unexpired response exists", () => {
  render(<LlmRawResponseDialog available={false} callId={callId} />)

  expect(screen.getByRole("button", { name: "原始响应不可用" })).toBeDisabled()
  expect(fetchMock).not.toHaveBeenCalled()
})
