import type { Metadata } from "next"
import Link from "next/link"
import { redirect } from "next/navigation"

import { AdminGateNotice } from "@/components/admin/admin-gate-notice"
import { LlmConfigurationWorkbench } from "@/components/admin/llm-configuration-workbench"
import {
  Page,
  PageActions,
  PageDescription,
  PageEyebrow,
  PageHeader,
  PageHeaderContent,
  PageTitle,
} from "@/components/layout/page"
import { Button } from "@/components/ui/button"
import { requireAdminView } from "@/lib/admin-guard"
import { createLlmConfigurationTransport, loadLlmWorkspace } from "@/lib/llm-configuration-client"

export const metadata: Metadata = { title: "LLM 配置" }

export default async function LlmConfigurationPage() {
  const guard = await requireAdminView()
  if (guard.kind !== "ok") return <AdminGateNotice failure={guard.kind} title="LLM 配置" />

  const result = await loadLlmWorkspace(createLlmConfigurationTransport(), guard.session)
  if (result.kind === "mfaRequired") redirect("/settings/security")
  if (result.kind === "anonymous" || result.kind === "forbidden") {
    return <AdminGateNotice failure={result.kind} title="LLM 配置" />
  }
  if (result.kind !== "ok") {
    return (
      <AdminGateNotice
        failure="unreachable"
        message="LLM 配置数据暂时不可用，请稍后重试。"
        title="LLM 配置"
      />
    )
  }

  return (
    <Page>
      <PageHeader>
        <PageHeaderContent>
          <PageEyebrow>平台管理 / AI 基础设施</PageEyebrow>
          <PageTitle>LLM 配置</PageTitle>
          <PageDescription>
            在线提交 OpenRouter 候选配置。平台完成固定最小探测后，原子创建并启用新的不可变版本。
          </PageDescription>
        </PageHeaderContent>
        <PageActions>
          <Button render={<Link href="/admin/llm-calls" />} variant="secondary">
            查看调用记录
          </Button>
        </PageActions>
      </PageHeader>
      <LlmConfigurationWorkbench workspace={result.workspace} />
    </Page>
  )
}
