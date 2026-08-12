import {
  DataRegion,
  DataRegionContent,
  Page,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { Spinner } from "@/components/ui/spinner"

export default function LlmConfigurationLoading() {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理 / AI 基础设施</PageEyebrow>
          <PageTitle>LLM 配置</PageTitle>
          <PageDescription>正在读取当前版本、历史记录和持久化变更状态。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <DataRegion>
        <DataRegionContent className="flex min-h-48 items-center justify-center p-5">
          <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            正在加载 LLM 配置…
          </span>
        </DataRegionContent>
      </DataRegion>
    </Page>
  )
}
