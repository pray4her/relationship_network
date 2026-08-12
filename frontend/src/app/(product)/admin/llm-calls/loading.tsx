import {
  DataRegion,
  Page,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageTitle,
  PageToolbar,
} from "@/components/layout/page"
import { Skeleton } from "@/components/ui/skeleton"

const toolbarSkeletons = ["scope", "type", "outcome", "metadata", "dates"]
const rowSkeletons = ["one", "two", "three", "four", "five", "six", "seven", "eight"]

export default function LlmCallListLoading() {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理 / AI 基础设施</PageEyebrow>
          <PageTitle>LLM 调用记录</PageTitle>
          <PageDescription>正在读取调用、结果和延迟元数据。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <PageToolbar>
        {toolbarSkeletons.map((key) => (
          <Skeleton className="h-16 w-40" key={key} />
        ))}
      </PageToolbar>
      <DataRegion className="flex flex-col gap-3 p-5">
        {rowSkeletons.map((key) => (
          <Skeleton className="h-12 w-full" key={key} />
        ))}
      </DataRegion>
    </Page>
  )
}
