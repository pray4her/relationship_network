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
          <Skeleton className="h-[var(--space-12)] max-w-xl" />
          <Skeleton className="max-w-2xl" variant="text" />
        </PageHeaderContent>
      </PageHeader>
      <PageSection>
        <PageSectionHeader>
          <PageSectionHeaderContent className="w-full">
            <Skeleton className="max-w-xs" variant="text" />
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DataRegion>
          <DataRegionContent className="divide-y divide-border-soft">
            {loadingRows.map((row) => (
              <div
                className="grid grid-cols-[minmax(10rem,1fr)_minmax(7rem,0.45fr)_minmax(8rem,0.55fr)] gap-[var(--space-6)] px-[var(--space-5)] py-[var(--space-4)] max-sm:grid-cols-[1fr_auto]"
                key={row}
              >
                <Skeleton variant="text" />
                <Skeleton className="max-sm:hidden" variant="text" />
                <Skeleton className="w-24" variant="text" />
              </div>
            ))}
          </DataRegionContent>
        </DataRegion>
      </PageSection>
    </Page>
  )
}
