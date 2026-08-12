import {
  DataRegion,
  Page,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { Skeleton } from "@/components/ui/skeleton"

const factSkeletons = [
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
]
const eventSkeletons = ["one", "two", "three", "four"]

export default function LlmCallDetailLoading() {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理 / AI 基础设施 / 调用详情</PageEyebrow>
          <PageTitle>LLM 调用详情</PageTitle>
          <PageDescription>正在读取请求事实和事件时间线。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <DataRegion className="grid grid-cols-2 gap-4 p-5 max-md:grid-cols-1">
        {factSkeletons.map((key) => (
          <Skeleton className="h-14 w-full" key={key} />
        ))}
      </DataRegion>
      <DataRegion className="flex flex-col gap-3 p-5">
        {eventSkeletons.map((key) => (
          <Skeleton className="h-20 w-full" key={key} />
        ))}
      </DataRegion>
    </Page>
  )
}
