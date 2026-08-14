import {
  DataRegion,
  Page,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { Skeleton } from "@/components/ui/skeleton"

const factSkeletons = ["one", "two", "three", "four", "five", "six", "seven"]

export default function TalentDetailLoading() {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>人才详情</PageTitle>
          <PageDescription>正在读取人才档案和来源追踪。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <DataRegion className="grid grid-cols-2 gap-4 p-5 max-md:grid-cols-1">
        {factSkeletons.map((key) => (
          <Skeleton className="h-14 w-full" key={key} />
        ))}
      </DataRegion>
    </Page>
  )
}
