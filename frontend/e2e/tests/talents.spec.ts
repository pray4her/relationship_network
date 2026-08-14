import { execFileSync } from "node:child_process"
import { existsSync } from "node:fs"
import { join } from "node:path"

import { expect, test } from "@playwright/test"

import { isAuthApiAvailable, registerOwner } from "./helpers"

const TALENT_ID = "22222222-2222-2222-2222-222222222222"

test.setTimeout(180_000)

function repoRoot(): string {
  let current = process.cwd()
  for (let index = 0; index < 5; index += 1) {
    if (existsSync(join(current, "compose.yaml"))) {
      return current
    }
    current = join(current, "..")
  }
  throw new Error("compose.yaml not found from Playwright working directory")
}

function seedLocalTalent(availability: "available" | "temporarily_unavailable"): void {
  const sql = [
    "INSERT INTO local_talents",
    "(id, canonical_person_id, display_name, current_affiliation, country, chinese_identity, h_index, total_citations, qs_top200_rank, world_top500_rank, has_contact, data_version, availability)",
    "VALUES",
    `('${TALENT_ID}', 'cp-e2e-001', 'E2E 人才', '示例大学', 'CN', '国内华人', 40, 3000, 10, 20, true, 'dv-seed-001', '${availability}')`,
    "ON CONFLICT (id) DO UPDATE SET availability = EXCLUDED.availability, last_synced_at = now();",
    "INSERT INTO talent_external_ids (external_id, kind, local_talent_id)",
    "VALUES",
    `('cp-e2e-001', 'canonical_person_id', '${TALENT_ID}'), ('src-e2e-001', 'source_id', '${TALENT_ID}')`,
    "ON CONFLICT (external_id) DO NOTHING;",
  ].join(" ")
  execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "relationship",
      "-d",
      "relationship_network",
      "-c",
      sql,
    ],
    { cwd: repoRoot(), stdio: "pipe" },
  )
}

async function signInFreshOwner(page: import("@playwright/test").Page): Promise<void> {
  const email = `talent-e2e-${Date.now()}@example.com`
  await registerOwner(page, { displayName: "人才查看者", email })
}

test("renders an available talent detail page", async ({ page }) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过人才详情")
  seedLocalTalent("available")
  await signInFreshOwner(page)
  await page.goto(`/talents/${TALENT_ID}`)
  await expect(page.getByRole("heading", { name: "E2E 人才" })).toBeVisible()
  await expect(page.getByText("可用", { exact: true })).toBeVisible()
  await expect(page.getByText("cp-e2e-001")).toBeVisible()
})

test("renders a temporarily unavailable talent detail page", async ({ page }) => {
  test.skip(!(await isAuthApiAvailable()), "auth API 未部署，跳过人才详情")
  seedLocalTalent("temporarily_unavailable")
  await signInFreshOwner(page)
  await page.goto(`/talents/${TALENT_ID}`)
  await expect(page.getByRole("heading", { name: "E2E 人才" })).toBeVisible()
  await expect(page.getByText("暂时不可用", { exact: true })).toBeVisible()
})
