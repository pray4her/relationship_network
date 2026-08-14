import { describe, expect, it } from "vitest"

import { buildJobActivationChecklistItems } from "@/components/jobs/job-activation-checklist"
import { isJobDetailTab, resolveJobDetailTab, truncateLabel } from "@/lib/job-detail-tabs"

describe("resolveJobDetailTab", () => {
  it("keeps a valid tab from the query string", () => {
    expect(
      resolveJobDetailTab("materials", {
        hasEditableDraft: true,
        matchingBlocked: true,
      }),
    ).toBe("materials")
  })

  it("defaults to requirement when matching is blocked", () => {
    expect(
      resolveJobDetailTab(undefined, {
        hasEditableDraft: false,
        matchingBlocked: true,
      }),
    ).toBe("requirement")
  })

  it("defaults to requirement when an editable draft exists", () => {
    expect(
      resolveJobDetailTab(["bogus"], {
        hasEditableDraft: true,
        matchingBlocked: false,
      }),
    ).toBe("requirement")
  })

  it("defaults to overview otherwise", () => {
    expect(
      resolveJobDetailTab(undefined, {
        hasEditableDraft: false,
        matchingBlocked: false,
      }),
    ).toBe("overview")
  })

  it("recognizes known tabs only", () => {
    expect(isJobDetailTab("overview")).toBe(true)
    expect(isJobDetailTab("requirement")).toBe(true)
    expect(isJobDetailTab("versions")).toBe(true)
    expect(isJobDetailTab("history")).toBe(true)
    expect(isJobDetailTab("materials")).toBe(true)
    expect(isJobDetailTab("events")).toBe(true)
    expect(isJobDetailTab("")).toBe(false)
    expect(isJobDetailTab("candidates")).toBe(false)
  })
})

describe("truncateLabel", () => {
  it("keeps short labels intact", () => {
    expect(truncateLabel("本科及以上学历")).toBe("本科及以上学历")
  })

  it("truncates long labels with an ellipsis", () => {
    const label = "要求具备良好的信息整理与多线程跟进能力"
    expect(truncateLabel(label, 12)).toBe(`${label.slice(0, 11)}…`)
  })
})

describe("buildJobActivationChecklistItems", () => {
  it("marks confirmed version and matching gate as done when clear", () => {
    const items = buildJobActivationChecklistItems({
      hasConfirmedVersion: true,
      matchingBlocked: false,
      materialCount: 2,
    })
    expect(items.map((item) => [item.id, item.done])).toEqual([
      ["confirmed-version", true],
      ["matching-gate", true],
      ["materials", true],
    ])
  })

  it("flags pending matching and materials", () => {
    const items = buildJobActivationChecklistItems({
      hasConfirmedVersion: false,
      matchingBlocked: true,
      materialCount: 0,
    })
    expect(items.every((item) => !item.done)).toBe(true)
    expect(items.find((item) => item.id === "matching-gate")?.tab).toBe("requirement")
    expect(items.find((item) => item.id === "materials")?.tab).toBe("materials")
  })
})
