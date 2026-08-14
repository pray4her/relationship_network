import {
  DescriptionDetails,
  DescriptionItem,
  DescriptionList,
  DescriptionTerm,
} from "@/components/layout/page"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { SearchInterpretation } from "@/lib/search-contract"

const fieldLabels: Readonly<Record<string, string>> = {
  qs_top200_rank: "QS 前 200 排名",
  world_top500_rank: "世界前 500 排名",
  h_index: "h 指数",
  total_citations: "总被引",
  chinese_identity: "华人身份",
  country: "国家/地区",
  current_affiliation: "现任机构",
}

const operatorLabels: Readonly<Record<string, string>> = {
  gte: "≥",
  lte: "≤",
  between: "介于",
  eq: "等于",
  in: "属于",
  match: "匹配",
  match_phrase: "短语匹配",
}

function formatValue(value: number | string | (number | string)[]): string {
  if (Array.isArray(value)) return value.join(" 至 ")
  return String(value)
}

function formatCondition(condition: {
  readonly field: string
  readonly operator: string
  readonly value: number | string | (number | string)[]
}): string {
  const field = fieldLabels[condition.field] ?? condition.field
  const operator = operatorLabels[condition.operator] ?? condition.operator
  return `${field} ${operator} ${formatValue(condition.value)}`
}

export function SearchInterpretationCard({
  interpretation,
}: {
  readonly interpretation: SearchInterpretation | null
}) {
  if (interpretation === null) return null

  const hasTopic = interpretation.research_topic_query.trim().length > 0
  const hasHard = interpretation.hard_conditions.length > 0
  const hasUnsupported = interpretation.unsupported_conditions.length > 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>搜索解释</CardTitle>
        <CardDescription>同一次结果中实际采用与未参与检索的条件。</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <DescriptionList>
          <DescriptionItem>
            <DescriptionTerm>研究主题查询</DescriptionTerm>
            <DescriptionDetails>
              {hasTopic ? (
                interpretation.research_topic_query
              ) : (
                <span className="text-muted-foreground">无（仅按硬条件结构化召回）</span>
              )}
            </DescriptionDetails>
          </DescriptionItem>
        </DescriptionList>

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline">硬条件</Badge>
            <span className="text-xs text-muted-foreground">不满足即排除，参与检索</span>
          </div>
          {hasHard ? (
            <ul className="flex flex-col gap-1 pl-1">
              {interpretation.hard_conditions.map((condition) => (
                <li key={condition.description || formatCondition(condition)} className="text-sm">
                  {condition.description || formatCondition(condition)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">无硬条件</p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline">未支持条件</Badge>
            <span className="text-xs text-muted-foreground">保留展示，不参与检索</span>
          </div>
          {hasUnsupported ? (
            <ul className="flex flex-col gap-1 pl-1">
              {interpretation.unsupported_conditions.map((condition) => (
                <li key={condition.description} className="text-sm text-muted-foreground">
                  {condition.description}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">无未支持条件</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
