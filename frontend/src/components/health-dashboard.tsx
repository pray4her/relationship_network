import {
  DataRegion,
  DataRegionContent,
  Page,
  PageActions,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
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

function StatusLabel({ online }: { readonly online: boolean }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-[var(--space-2)] font-mono text-[length:var(--text-caption)] tracking-[var(--tracking-label)]">
      <span
        aria-hidden="true"
        className={cn(
          "size-[var(--space-2)] rounded-[var(--radius-full)]",
          online ? "bg-success" : "bg-destructive",
        )}
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
    <Page data-state={health.status}>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台健康状态</PageEyebrow>
          <PageTitle id="health-title">{isReady ? "系统运行正常" : "部分服务不可用"}</PageTitle>
          <PageDescription>
            {isReady
              ? "核心基础设施已连通，可以继续使用平台功能。"
              : "平台已启动，但部分依赖仍在恢复。请检查下方服务状态。"}
          </PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Badge variant={isReady ? "success" : "destructive"}>
            {isReady ? "就绪" : "需要处理"}
          </Badge>
          <Badge variant="secondary">本地 MVP</Badge>
        </PageActions>
      </PageHeader>

      <PageSection aria-labelledby="services-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="services-heading">服务状态</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent className="divide-y divide-border-soft">
            {services.map((service, index) => (
              <article
                className="flex min-h-[var(--control-height-lg)] items-center gap-[var(--space-4)] px-[var(--space-5)] py-[var(--space-4)] max-sm:px-[var(--space-4)]"
                data-state={service.status}
                key={service.name}
              >
                <span className="w-7 shrink-0 font-mono text-[length:var(--text-caption)] text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="m-0 text-[length:var(--text-body-md)] font-medium">
                    {service.label}
                  </h3>
                  <p className="m-0 text-[length:var(--text-body-sm)] text-muted-foreground">
                    {service.status === "ok" ? "连接正常" : "暂时不可用"}
                  </p>
                </div>
                <StatusLabel online={service.status === "ok"} />
              </article>
            ))}
          </DataRegionContent>
        </DataRegion>
        <p className="m-0 text-[length:var(--text-body-sm)] text-muted-foreground">
          刷新状态：重新加载页面。
        </p>
      </PageSection>
    </Page>
  )
}

export function HealthDashboard({ health }: HealthDashboardProps) {
  if (health.kind === "ready") {
    return <ConnectedDashboard health={health.value} />
  }

  return (
    <Page data-state="unreachable">
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台健康状态</PageEyebrow>
          <PageTitle id="health-title">服务正在恢复</PageTitle>
          <PageDescription>{health.reason}</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Badge variant="destructive">连接中断</Badge>
        </PageActions>
      </PageHeader>
      <Alert variant="destructive">
        <AlertTitle>无法连接 API</AlertTitle>
        <AlertDescription>请确认 Docker 服务已启动，然后刷新页面。</AlertDescription>
      </Alert>
    </Page>
  )
}
