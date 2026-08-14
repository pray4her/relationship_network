import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import {
  DescriptionDetails,
  DescriptionItem,
  DescriptionList,
  DescriptionTerm,
  Page,
  PageActions,
  PageDescription,
  PageHeader,
  PageHeaderContent,
  PageSection,
  PageSectionHeader,
  PageSectionHeaderContent,
  PageSectionTitle,
  PageTitle,
} from "@/components/layout/page"
import { StatusBadge } from "@/components/status-badge"
import { talentStatusMeta } from "@/components/talents/talent-status"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { formatDateTime } from "@/lib/format"
import { databaseUuidSchema } from "@/lib/llm-configuration-contract"
import { createTalentsTransport, loadTalentDetail } from "@/lib/talents-client"

type TalentDetailPageProps = {
  readonly params: Promise<{ readonly id: string }>
}

export const metadata: Metadata = {
  title: "人才详情",
}

function NoticePage({ children }: { readonly children: React.ReactNode }) {
  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle>人才详情</PageTitle>
          <PageDescription>查看本地人才的最新已知信息与来源追踪。</PageDescription>
        </PageHeaderContent>
      </PageHeader>
      <Alert>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </Page>
  )
}

function optionalRank(value: number | null): string {
  return value === null ? "—" : String(value)
}

export default async function TalentDetailPage({ params }: TalentDetailPageProps) {
  const { id } = await params
  if (!databaseUuidSchema.safeParse(id).success) {
    notFound()
  }

  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value
  if (!session) {
    return (
      <NoticePage>
        请先
        <Link className="font-medium underline underline-offset-4" href="/login">
          登录
        </Link>
        。
      </NoticePage>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return <NoticePage>登录状态无效，请重新登录。</NoticePage>
  }

  const detail = await loadTalentDetail(createTalentsTransport(), session, id)
  if (detail.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (detail.kind === "notFound") {
    notFound()
  }
  if (detail.kind !== "ok") {
    return <NoticePage>人才详情暂时不可用，请稍后再试。</NoticePage>
  }

  const { talent } = detail

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageTitle id="talent-detail-heading">{talent.display_name}</PageTitle>
          <PageDescription>{talent.current_affiliation}</PageDescription>
        </PageHeaderContent>
        <PageActions>
          <StatusBadge {...talentStatusMeta[talent.availability]} />
        </PageActions>
      </PageHeader>

      <PageSection aria-labelledby="profile-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="profile-heading">人才档案</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DescriptionList>
          <DescriptionItem>
            <DescriptionTerm>现任机构</DescriptionTerm>
            <DescriptionDetails>{talent.current_affiliation}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>国家/地区</DescriptionTerm>
            <DescriptionDetails>{talent.country}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>华人身份</DescriptionTerm>
            <DescriptionDetails>{talent.chinese_identity}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>h 指数</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">{talent.h_index}</DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>总被引</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {talent.total_citations}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>QS 前 200 排名</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {optionalRank(talent.qs_top200_rank)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>世界前 500 排名</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {optionalRank(talent.world_top500_rank)}
            </DescriptionDetails>
          </DescriptionItem>
        </DescriptionList>
      </PageSection>

      <PageSection aria-labelledby="source-heading">
        <PageSectionHeader>
          <PageSectionHeaderContent>
            <PageSectionTitle id="source-heading">来源追踪</PageSectionTitle>
          </PageSectionHeaderContent>
        </PageSectionHeader>
        <DescriptionList>
          <DescriptionItem>
            <DescriptionTerm>规范人物 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {talent.canonical_person_id}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>数据版本</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {talent.data_version}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>最后同步时间</DescriptionTerm>
            <DescriptionDetails className="tabular-nums">
              {formatDateTime(talent.last_synced_at)}
            </DescriptionDetails>
          </DescriptionItem>
          <DescriptionItem>
            <DescriptionTerm>历史来源 ID</DescriptionTerm>
            <DescriptionDetails className="break-all font-mono text-sm">
              {talent.historical_source_ids.length === 0
                ? "—"
                : talent.historical_source_ids.join(", ")}
            </DescriptionDetails>
          </DescriptionItem>
        </DescriptionList>
      </PageSection>
    </Page>
  )
}
