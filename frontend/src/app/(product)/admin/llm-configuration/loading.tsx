import {
  Page,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { Card, CardContent } from "@/components/ui/card"
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
      <Card variant="outlined">
        <CardContent className="flex min-h-48 items-center justify-center">
          <Spinner label="正在加载 LLM 配置…" />
        </CardContent>
      </Card>
    </Page>
  )
}
