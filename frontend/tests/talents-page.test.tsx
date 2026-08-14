import { render, screen } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

import { loadAuthSession } from "@/lib/auth-client"
import { loadTalentDetail } from "@/lib/talents-client"
import type { TalentView } from "@/lib/talents-contract"
import TalentDetailPage from "../src/app/(product)/talents/[id]/page"

const talentId = "11111111-1111-1111-1111-111111111111"

const talent: TalentView = {
  id: talentId,
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
}

vi.mock("next/headers", () => ({
  cookies: async () => ({ get: () => ({ value: "session-token" }) }),
}))

vi.mock("next/navigation", () => ({
  notFound: vi.fn(),
  redirect: vi.fn(),
}))

vi.mock("@/lib/auth-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-client")>()
  return {
    ...actual,
    createAuthTransport: vi.fn(() => ({})),
    loadAuthSession: vi.fn(),
  }
})

vi.mock("@/lib/talents-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/talents-client")>()
  return {
    ...actual,
    createTalentsTransport: vi.fn(() => ({})),
    loadTalentDetail: vi.fn(),
  }
})

const mockedLoadAuthSession = vi.mocked(loadAuthSession)
const mockedLoadTalentDetail = vi.mocked(loadTalentDetail)

beforeEach(() => {
  vi.clearAllMocks()
  mockedLoadAuthSession.mockResolvedValue({
    kind: "authenticated",
    renewedSession: null,
    view: {
      permissions: [],
      role: "owner",
      tenant: { id: "tenant-1", name: "示例租户", slug: "demo" },
      user: {
        display_name: "张三",
        email: "owner@example.com",
        id: "user-owner",
        is_platform_admin: false,
      },
    },
  })
})

test("renders header fields, availability, and source tracking", async () => {
  mockedLoadTalentDetail.mockResolvedValue({ kind: "ok", talent })

  render(await TalentDetailPage({ params: Promise.resolve({ id: talentId }) }))

  expect(screen.getByRole("heading", { name: "Wei Zhang" })).toBeVisible()
  expect(screen.getAllByText("Tsinghua University").length).toBeGreaterThan(0)
  expect(screen.getByText("可用")).toBeVisible()
  expect(screen.getByText("cp-seed-001")).toBeVisible()
  expect(screen.getByText("dv-seed-001")).toBeVisible()
  expect(screen.getByText("src-openalex-001, src-orcid-001")).toBeVisible()
})

test("shows the temporarily-unavailable badge", async () => {
  mockedLoadTalentDetail.mockResolvedValue({
    kind: "ok",
    talent: { ...talent, availability: "temporarily_unavailable" },
  })

  render(await TalentDetailPage({ params: Promise.resolve({ id: talentId }) }))

  expect(screen.getByText("暂时不可用")).toBeVisible()
})
