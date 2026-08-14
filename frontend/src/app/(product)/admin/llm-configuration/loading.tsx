import { Page, PageHeader, PageHeaderContent } from "@/components/layout/page"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

const loadingCards = ["current", "candidate", "progress", "history"] as const

export default function LlmConfigurationLoading() {
  return (
    <Page aria-busy="true" aria-label="正在加载 LLM 配置">
      <PageHeader>
        <PageHeaderContent>
          <Skeleton className="h-12 max-w-xl" />
          <Skeleton className="h-4 max-w-2xl" />
        </PageHeaderContent>
      </PageHeader>
      <div className="flex flex-col gap-6">
        {loadingCards.map((card) => (
          <Card key={card}>
            <CardHeader>
              <Skeleton className="h-5 max-w-48" />
              <Skeleton className="h-4 max-w-72" />
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Skeleton className="h-4 max-w-full" />
              <Skeleton className="h-4 max-w-sm" />
              <Skeleton className="h-9 max-w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </Page>
  )
}
