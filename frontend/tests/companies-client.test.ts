import { expect, test } from "vitest"

import {
  archiveCompany,
  type CompaniesTransport,
  CompaniesTransportError,
  type CompaniesTransportResponse,
  createCompany,
  loadCompanies,
} from "../src/lib/companies-client"

const companyBody = {
  id: "company-1",
  name: "示例企业",
  profile_text: "简介",
  status: "active",
  created_at: "2026-08-04T12:00:00+00:00",
  updated_at: "2026-08-04T12:00:00+00:00",
  archived_at: null,
} as const

class ScriptedCompaniesTransport implements CompaniesTransport {
  readonly #handler: () => Promise<CompaniesTransportResponse>

  constructor(handler: () => Promise<CompaniesTransportResponse>) {
    this.#handler = handler
  }

  list(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  get(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  create(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  update(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  archive(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  listDocuments(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  uploadDocument(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }

  listEvents(): Promise<CompaniesTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: CompaniesTransportResponse): CompaniesTransport {
  return new ScriptedCompaniesTransport(() => Promise.resolve(response))
}

test("parses the company list on success", async () => {
  const result = await loadCompanies(fixedTransport({ body: [companyBody], status: 200 }), "s")
  expect(result).toEqual({ kind: "ok", companies: [companyBody] })
})

test("maps company quota exceeded on create", async () => {
  const result = await createCompany(
    fixedTransport({ body: { detail: "company_quota_exceeded" }, status: 409 }),
    "s",
    { name: "超额" },
  )
  expect(result).toEqual({ kind: "quotaExceeded" })
})

test("maps forbidden without companies permission", async () => {
  const result = await loadCompanies(
    fixedTransport({ body: { detail: "permission_denied" }, status: 403 }),
    "s",
  )
  expect(result).toEqual({ kind: "forbidden" })
})

test("parses archived company after archive", async () => {
  const archived = {
    ...companyBody,
    status: "archived",
    archived_at: "2026-08-04T13:00:00+00:00",
  } as const
  const result = await archiveCompany(
    fixedTransport({ body: archived, status: 200 }),
    "s",
    "company-1",
  )
  expect(result).toEqual({ kind: "ok", company: archived })
})

test("returns unreachable when transport fails", async () => {
  const transport = new ScriptedCompaniesTransport(() =>
    Promise.reject(new CompaniesTransportError("down")),
  )
  const result = await loadCompanies(transport, "s")
  expect(result).toEqual({ kind: "unreachable" })
})
