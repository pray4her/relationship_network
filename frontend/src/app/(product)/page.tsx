import { connection } from "next/server"

import { HealthDashboard } from "@/components/health-dashboard"
import { createReadinessTransport, loadDashboardHealth } from "@/lib/health-client"

export default async function HomePage() {
  await connection()
  const health = await loadDashboardHealth(createReadinessTransport())
  return <HealthDashboard health={health} />
}
