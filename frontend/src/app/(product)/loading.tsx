import {
  DataRegion,
  DataRegionContent,
  Page,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
} from "@/components/layout/page"
import { Skeleton } from "@/components/ui/skeleton"

const loadingRows = ["row-1", "row-2", "row-3", "row-4", "row-5"] as const

export default function ProductPageLoading() {
  return (
    <Page aria-busy="true" aria-label="正在加载页面">
      <PageHeader>
        <PageHeaderContent>
          <Skeleton className="h-12 max-w-xl" />
          <Skeleton className="h-4 max-w-2xl" />
        </PageHeaderContent>
      </PageHeader>
      <PageSection>
        <PageSectionHeader>
          <PageSectionHeaderContent className="w-full">
            <Skeleton className="h-4 max-w-xs" />
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent className="divide-y divide-border">
            {loadingRows.map((row) => (
              <div
                className="grid grid-cols-[minmax(10rem,1fr)_minmax(7rem,0.45fr)_minmax(8rem,0.55fr)] gap-6 px-5 py-4 max-sm:grid-cols-[1fr_auto]"
                key={row}
              >
                <Skeleton className="h-4" />
                <Skeleton className="h-4 max-sm:hidden" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
