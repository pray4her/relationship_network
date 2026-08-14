import { render, screen } from "@testing-library/react"
import { expect, test } from "vitest"

import { HealthDashboard } from "../src/components/health-dashboard"

test("shows every dependency as available when the platform is ready", () => {
  // Given the API reports every platform dependency as healthy
  const health = {
    dependencies: [
      { name: "postgres", status: "ok" },
      { name: "redis", status: "ok" },
      { name: "object_storage", status: "ok" },
    ],
    status: "ok",
  } as const

  // When the health dashboard is rendered
  render(<HealthDashboard health={{ kind: "ready", value: health }} />)

  // Then operators see a ready summary and all dependency labels
  expect(screen.getByRole("heading", { level: 1, name: "系统运行正常" })).toBeInTheDocument()
  expect(screen.getByText("FastAPI")).toBeInTheDocument()
  expect(screen.getByText("PostgreSQL")).toBeInTheDocument()
  expect(screen.getByText("Redis")).toBeInTheDocument()
  expect(screen.getByText("MinIO 对象存储")).toBeInTheDocument()
  expect(screen.getAllByText("在线")).toHaveLength(4)
})

test("shows individual dependency failures while the API remains available", () => {
  const health = {
    dependencies: [
      { name: "postgres", status: "ok" },
      { name: "redis", status: "unavailable" },
      { name: "object_storage", status: "ok" },
    ],
    status: "degraded",
  } as const

  render(<HealthDashboard health={{ kind: "ready", value: health }} />)

  expect(screen.getByRole("heading", { level: 1, name: "部分服务不可用" })).toBeInTheDocument()
  expect(screen.getByText("FastAPI")).toBeInTheDocument()
  expect(screen.getAllByText("在线")).toHaveLength(3)
  expect(screen.getByText("离线")).toBeInTheDocument()
})

test("shows an actionable unavailable state when the API cannot be reached", () => {
  // Given the API health endpoint is unavailable
  const health = { kind: "unreachable", reason: "API 暂时无法连接" } as const

  // When the health dashboard is rendered
  render(<HealthDashboard health={health} />)

  // Then operators see the degraded state and recovery guidance
  expect(screen.getByRole("heading", { level: 1, name: "服务正在恢复" })).toBeInTheDocument()
  expect(screen.getByText("API 暂时无法连接")).toBeInTheDocument()
  expect(screen.getByText("请确认 Docker 服务已启动，然后刷新页面。")).toBeInTheDocument()
})
