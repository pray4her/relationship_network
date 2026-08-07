import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { DashboardHealth, HealthResponse } from "@/lib/health-contract"
import { cn } from "@/lib/utils"

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

function Masthead({ recovery }: { readonly recovery?: boolean }) {
  return (
    <header className="flex items-center justify-between border-b py-4">
      <a
        className="font-mono text-sm font-semibold tracking-widest"
        href="/"
        aria-label="关系网络平台首页"
      >
        RELATIONSHIP / NETWORK
      </a>
      <Badge variant={recovery ? "destructive" : "secondary"}>
        {recovery ? "MVP · RECOVERY" : "MVP · LOCAL"}
      </Badge>
    </header>
  )
}

function Footer({ left, right }: { readonly left: string; readonly right: string }) {
  return (
    <footer className="mt-auto flex items-center justify-between border-t py-4 font-mono text-xs tracking-wider text-muted-foreground">
      <span>{left}</span>
      <span>{right}</span>
    </footer>
  )
}

function StatusPill({ online }: { readonly online: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 font-mono text-xs tracking-wider">
      <span
        aria-hidden="true"
        className={cn("size-2 rounded-full", online ? "bg-success" : "bg-destructive")}
      />
      {online ? "ONLINE" : "OFFLINE"}
    </span>
  )
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
    <main
      className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-6"
      data-state={health.status}
    >
      <Masthead />

      <section aria-labelledby="health-title" className="py-16 md:py-20">
        <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
          PLATFORM READINESS / 平台就绪状态
        </p>
        <h1
          className="mt-4 max-w-3xl text-4xl font-bold tracking-tight md:text-5xl"
          id="health-title"
        >
          {isReady ? "系统运行正常" : "部分服务不可用"}
        </h1>
        <p className="mt-5 max-w-[65ch] text-base text-muted-foreground">
          {isReady
            ? "核心基础设施已连通，后续产品开发可以开始。"
            : "平台已启动，但部分依赖仍在恢复。请检查下方状态。"}
        </p>
      </section>

      <section aria-label="平台服务状态">
        <Card>
          <CardContent className="divide-y p-0">
            {services.map((service, index) => (
              <article
                className="flex items-center gap-4 px-4 py-3.5"
                data-state={service.status}
                key={service.name}
              >
                <span className="w-7 font-mono text-xs text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-sm font-medium">{service.label}</h2>
                  <p className="text-xs text-muted-foreground">
                    {service.status === "ok" ? "连接正常" : "暂时不可用"}
                  </p>
                </div>
                <StatusPill online={service.status === "ok"} />
              </article>
            ))}
          </CardContent>
        </Card>
      </section>

      <Footer left="API / WORKER / STORAGE" right="刷新状态：重新加载页面" />
    </main>
  )
}

export function HealthDashboard({ health }: HealthDashboardProps) {
  if (health.kind === "ready") {
    return <ConnectedDashboard health={health.value} />
  }

  return (
    <main
      className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-6"
      data-state="unreachable"
    >
      <Masthead recovery />

      <section aria-labelledby="health-title" className="flex flex-1 flex-col justify-center py-16">
        <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
          CONNECTION INTERRUPTED / 连接中断
        </p>
        <h1
          className="mt-4 max-w-3xl text-4xl font-bold tracking-tight md:text-5xl"
          id="health-title"
        >
          服务正在恢复
        </h1>
        <p className="mt-5 max-w-[65ch] text-base text-muted-foreground">{health.reason}</p>
        <p className="mt-4 w-fit rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm">
          请确认 Docker 服务已启动，然后刷新页面。
        </p>
      </section>

      <Footer left="API CONNECTION REQUIRED" right="状态不会影响已保存的数据" />
    </main>
  )
}
