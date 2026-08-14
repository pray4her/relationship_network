import { expect, test } from "vitest"

import {
  loadTalentDetail,
  type TalentsTransport,
  type TalentsTransportResponse,
} from "../src/lib/talents-client"

const talentBody = {
  id: "11111111-1111-1111-1111-111111111111",
  canonical_person_id: "cp-seed-001",
  display_name: "Wei Zhang",
  current_affiliation: "Tsinghua University",
  country: "CN",
  chinese_identity: "国内华人",
  h_index: 42,
  total_citations: 3180,
  qs_top200_rank: 25,
  world_top500_rank: 18,
  has_contact: true,
  data_version: "dv-seed-001",
  availability: "available",
  last_synced_at: "2026-08-13T12:00:00+00:00",
  historical_source_ids: ["src-openalex-001", "src-orcid-001"],
} as const

class ScriptedTalentsTransport implements TalentsTransport {
  readonly #handler: () => Promise<TalentsTransportResponse>

  constructor(handler: () => Promise<TalentsTransportResponse>) {
    this.#handler = handler
  }

  get(): Promise<TalentsTransportResponse> {
    return this.#handler()
  }
}

function fixedTransport(response: TalentsTransportResponse): TalentsTransport {
  return new ScriptedTalentsTransport(() => Promise.resolve(response))
}

test("parses a talent on success", async () => {
  const result = await loadTalentDetail(
    fixedTransport({ body: talentBody, status: 200 }),
    "session",
    talentBody.id,
  )
  expect(result).toEqual({ kind: "ok", talent: talentBody })
})

test("maps 404 to notFound", async () => {
  const result = await loadTalentDetail(
    fixedTransport({ body: { detail: "talent_not_found" }, status: 404 }),
    "session",
    "missing",
  )
  expect(result).toEqual({ kind: "notFound" })
})

test("maps 401 to anonymous", async () => {
  const result = await loadTalentDetail(
    fixedTransport({ body: { detail: "not_authenticated" }, status: 401 }),
    "session",
    talentBody.id,
  )
  expect(result).toEqual({ kind: "anonymous" })
})

test("maps 403 mfa_required to mfaRequired", async () => {
  const result = await loadTalentDetail(
    fixedTransport({ body: { detail: "mfa_required" }, status: 403 }),
    "session",
    talentBody.id,
  )
  expect(result).toEqual({ kind: "mfaRequired" })
})

test("maps non-200 to unreachable", async () => {
  const result = await loadTalentDetail(
    fixedTransport({ body: null, status: 500 }),
    "session",
    talentBody.id,
  )
  expect(result).toEqual({ kind: "unreachable" })
})
