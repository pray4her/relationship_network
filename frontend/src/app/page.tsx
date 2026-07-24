import { connection } from "next/server"

import { AccountPanel } from "../components/account-panel"
import { HealthDashboard } from "../components/health-dashboard"
import { createReadinessTransport, loadDashboardHealth } from "../lib/health-client"

export default async function HomePage() {
  await connection()
  const health = await loadDashboardHealth(createReadinessTransport())
  return (
    <>
      <AccountPanel />
      <HealthDashboard health={health} />
    </>
  )
}
