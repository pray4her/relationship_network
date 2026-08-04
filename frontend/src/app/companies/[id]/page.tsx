import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import {
  archiveCompanyAction,
  updateCompanyAction,
  uploadCompanyDocumentAction,
} from "@/app/actions/companies"
import { AccountPanel } from "@/components/account-panel"
import { CompanyArchiveButton } from "@/components/companies/company-archive-button"
import { CompanyDocumentUpload } from "@/components/companies/company-document-upload"
import { CompanyEditForm } from "@/components/companies/company-edit-form"
import { createAuthTransport, loadAuthSession, SESSION_COOKIE_NAME } from "@/lib/auth-client"
import { createCompaniesTransport, loadCompanyDetail } from "@/lib/companies-client"

type CompanyDetailPageProps = {
  readonly params: Promise<{ readonly id: string }>
}

export const metadata: Metadata = {
  title: "企业详情 · Relationship Network",
}

const eventLabels: Record<string, string> = {
  "company.create": "创建",
  "company.update": "编辑",
  "company.archive": "归档",
  "company.document_upload": "上传文档",
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

export default async function CompanyDetailPage({ params }: CompanyDetailPageProps) {
  const { id } = await params
  const store = await cookies()
  const session = store.get(SESSION_COOKIE_NAME)?.value

  if (!session) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业详情</h1>
          <p className="notice">
            请先<Link href="/login">登录</Link>。
          </p>
        </section>
      </main>
    )
  }

  const auth = await loadAuthSession(createAuthTransport(), session)
  if (auth.kind !== "authenticated") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业详情</h1>
          <p className="notice">登录状态无效，请重新登录。</p>
        </section>
      </main>
    )
  }

  if (!auth.view.permissions.includes("companies:read")) {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业详情</h1>
          <p className="notice">你没有查看企业的权限。</p>
        </section>
      </main>
    )
  }

  const detail = await loadCompanyDetail(createCompaniesTransport(), session, id)
  if (detail.kind === "mfaRequired") {
    redirect("/settings/security")
  }
  if (detail.kind === "notFound") {
    notFound()
  }
  if (detail.kind !== "ok") {
    return (
      <main className="page-shell">
        <AccountPanel />
        <section className="panel">
          <h1 className="panel-title">企业详情</h1>
          <p className="notice">企业详情暂时不可用，请稍后再试。</p>
        </section>
      </main>
    )
  }

  const { company, documents, events } = detail
  const canManage = auth.view.permissions.includes("companies:manage")
  const isActive = company.status === "active"

  return (
    <main className="page-shell">
      <AccountPanel />

      <section className="panel" aria-labelledby="company-detail-heading">
        <p className="notice">
          <Link href="/companies">← 返回企业列表</Link>
        </p>
        <h1 className="panel-title" id="company-detail-heading">
          {company.name}
        </h1>
        <p>
          <span className={isActive ? "tag" : "tag tag-muted"}>
            {isActive ? "活跃" : "已归档"}
          </span>
        </p>
        <p className="notice">{company.profile_text || "暂无企业简介。"}</p>
      </section>

      {canManage && isActive ? (
        <section className="panel" aria-labelledby="edit-company-heading">
          <h2 className="panel-title" id="edit-company-heading">
            编辑企业
          </h2>
          <CompanyEditForm
            action={updateCompanyAction}
            companyId={company.id}
            name={company.name}
            profileText={company.profile_text}
          />
          <CompanyArchiveButton action={archiveCompanyAction} companyId={company.id} />
        </section>
      ) : null}

      <section className="panel" aria-labelledby="documents-heading">
        <h2 className="panel-title" id="documents-heading">
          企业文档
        </h2>
        {documents.length === 0 ? (
          <p className="notice">尚未上传文档。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>大小</th>
                <th>抽取文本预览</th>
                <th>上传时间</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.id}>
                  <td>{document.original_filename}</td>
                  <td>{document.byte_size} B</td>
                  <td>{document.extracted_text.slice(0, 120) || "—"}</td>
                  <td>{formatDateTime(document.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {canManage && isActive ? (
          <CompanyDocumentUpload action={uploadCompanyDocumentAction} companyId={company.id} />
        ) : null}
      </section>

      <section className="panel" aria-labelledby="events-heading">
        <h2 className="panel-title" id="events-heading">
          操作记录
        </h2>
        {events.length === 0 ? (
          <p className="notice">暂无操作记录。</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>结果</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{formatDateTime(event.created_at)}</td>
                  <td>{eventLabels[event.action] ?? event.action}</td>
                  <td>{event.result}</td>
                  <td>{event.detail || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  )
}
