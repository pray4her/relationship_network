import Link from "next/link"

import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { SearchHitSnapshot } from "@/lib/search-contract"

const sortColumns = [
  { key: "display_name", label: "姓名" },
  { key: "current_affiliation", label: "现任机构" },
  { key: "country", label: "国家/地区" },
  { key: "chinese_identity", label: "华人身份" },
  { key: "h_index", label: "h 指数" },
  { key: "total_citations", label: "总被引" },
  { key: "qs_top200_rank", label: "QS 排名" },
  { key: "world_top500_rank", label: "世界排名" },
] as const

function optionalRank(value: number | null): string {
  return value === null ? "—" : String(value)
}

function SortableHead({
  label,
  sortKey,
  current,
}: {
  readonly label: string
  readonly sortKey: string
  readonly current: string
}) {
  const active = current === sortKey
  return (
    <TableHead
      numeric={
        sortKey !== "display_name" &&
        sortKey !== "current_affiliation" &&
        sortKey !== "country" &&
        sortKey !== "chinese_identity"
      }
    >
      <Link
        href={{ query: { sort: sortKey } }}
        aria-current={active ? "page" : undefined}
        className={
          active
            ? "font-semibold text-foreground underline underline-offset-4"
            : "text-muted-foreground hover:text-foreground"
        }
      >
        {label}
      </Link>
    </TableHead>
  )
}

export function SearchHitsTable({
  hits,
  sort,
  hasResearchTopic,
  leftRelevanceOrder,
}: {
  readonly hits: readonly SearchHitSnapshot[]
  readonly sort: string
  readonly hasResearchTopic: boolean
  readonly leftRelevanceOrder: boolean
}) {
  return (
    <div className="flex flex-col gap-2">
      {leftRelevanceOrder ? (
        <p className="text-xs text-muted-foreground">已按所选键改排，不再按相关性次序。</p>
      ) : null}
      <Table>
        <TableHeader>
          <TableRow>
            {hasResearchTopic ? (
              <TableHead numeric>
                <Link
                  href={{ query: {} }}
                  aria-current={sort === "semantic_score" ? "page" : undefined}
                  className={
                    sort === "semantic_score"
                      ? "font-semibold text-foreground underline underline-offset-4"
                      : "text-muted-foreground hover:text-foreground"
                  }
                >
                  相关性
                </Link>
              </TableHead>
            ) : null}
            {sortColumns.map((column) => (
              <SortableHead
                key={column.key}
                label={column.label}
                sortKey={column.key}
                current={sort}
              />
            ))}
            <TableHead>联系方式</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {hits.map((hit) => (
            <TableRow key={hit.id}>
              {hasResearchTopic ? (
                <TableCell numeric>
                  {hit.semantic_score === null ? "—" : hit.semantic_score.toFixed(3)}
                </TableCell>
              ) : null}
              <TableCell>
                <Link
                  className="font-medium underline underline-offset-4"
                  href={`/talents/${hit.local_talent_id}`}
                >
                  {hit.display_name}
                </Link>
              </TableCell>
              <TableCell>{hit.current_affiliation}</TableCell>
              <TableCell>{hit.country}</TableCell>
              <TableCell>{hit.chinese_identity}</TableCell>
              <TableCell numeric>{hit.h_index}</TableCell>
              <TableCell numeric>{hit.total_citations}</TableCell>
              <TableCell numeric>{optionalRank(hit.qs_top200_rank)}</TableCell>
              <TableCell numeric>{optionalRank(hit.world_top500_rank)}</TableCell>
              <TableCell>
                {hit.has_contact ? (
                  <Badge variant="outline">有联系方式</Badge>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
