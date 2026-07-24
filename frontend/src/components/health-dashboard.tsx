import { Badge } from "@/components/ui/badge"
import type { DashboardHealth, HealthResponse } from "@/lib/health-contract"

const dependencyLabels = {
  object_storage: "MinIO 对象存储",
  postgres: "PostgreSQL",
  redis: "Redis",
} as const

type HealthDashboardProps = {
  readonly health: DashboardHealth
}

type ConnectedDashboardProps = {
  readonly health: HealthResponse
}

function ConnectedDashboard({ health }: ConnectedDashboardProps) {
  const isReady = health.status === "ok"
  const services = [
    { label: "FastAPI", name: "api", status: "ok" as const },
    ...health.dependencies.map((dependency) => ({
      ...dependency,
      label: dependencyLabels[dependency.name],
    })),
  ]

  return (
    <main className="dashboard-shell" data-state={health.status}>
      <header className="masthead">
        <a className="brand" href="/" aria-label="关系网络平台首页">
          RELATIONSHIP / NETWORK
        </a>
        <Badge className="environment-badge">MVP · LOCAL</Badge>
      </header>

      <section className="hero" aria-labelledby="health-title">
        <div className="signal-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="eyebrow">PLATFORM READINESS / 平台就绪状态</p>
        <h1 id="health-title">{isReady ? "系统运行正常" : "部分服务不可用"}</h1>
        <p className="hero-copy">
          {isReady
            ? "核心基础设施已连通，后续产品开发可以开始。"
            : "平台已启动，但部分依赖仍在恢复。请检查下方状态。"}
        </p>
      </section>

      <section className="service-grid" aria-label="平台服务状态">
        {services.map((service, index) => (
          <article className="service-card" data-state={service.status} key={service.name}>
            <div className="service-index">{String(index + 1).padStart(2, "0")}</div>
            <div>
              <h2>{service.label}</h2>
              <p>{service.status === "ok" ? "连接正常" : "暂时不可用"}</p>
            </div>
            <span className="status-pill">
              <span className="status-dot" aria-hidden="true" />
              {service.status === "ok" ? "ONLINE" : "OFFLINE"}
            </span>
          </article>
        ))}
      </section>

      <footer className="dashboard-footer">
        <span>API / WORKER / STORAGE</span>
        <span>刷新状态：重新加载页面</span>
      </footer>
    </main>
  )
}

export function HealthDashboard({ health }: HealthDashboardProps) {
  if (health.kind === "ready") {
    return <ConnectedDashboard health={health.value} />
  }

  return (
    <main className="dashboard-shell" data-state="unreachable">
      <header className="masthead">
        <a className="brand" href="/" aria-label="关系网络平台首页">
          RELATIONSHIP / NETWORK
        </a>
        <Badge className="environment-badge" mode="recovery">
          MVP · RECOVERY
        </Badge>
      </header>

      <section className="hero hero-unreachable" aria-labelledby="health-title">
        <div className="signal-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="eyebrow">CONNECTION INTERRUPTED / 连接中断</p>
        <h1 id="health-title">服务正在恢复</h1>
        <p className="hero-copy">{health.reason}</p>
        <p className="recovery-copy">请确认 Docker 服务已启动，然后刷新页面。</p>
      </section>

      <footer className="dashboard-footer">
        <span>API CONNECTION REQUIRED</span>
        <span>状态不会影响已保存的数据</span>
      </footer>
    </main>
  )
}
