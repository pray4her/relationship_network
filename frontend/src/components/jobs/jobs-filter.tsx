"use client"

import { useRouter, useSearchParams } from "next/navigation"
import type { JobCompanyOption } from "@/components/jobs/job-create-form"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { JobStatus } from "@/lib/jobs-contract"

const ALL = "__all__"

const statusOptions: readonly { readonly value: JobStatus; readonly label: string }[] = [
  { value: "draft", label: "草稿" },
  { value: "active", label: "活跃" },
  { value: "closed", label: "已关闭" },
  { value: "archived", label: "已归档" },
]

type JobsFilterProps = {
  readonly companies: readonly JobCompanyOption[]
}

export function JobsFilter({ companies }: JobsFilterProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const status = searchParams.get("status") ?? ""
  const companyId = searchParams.get("company_id") ?? ""

  function applyFilter(next: { status?: string; companyId?: string }) {
    const params = new URLSearchParams(searchParams.toString())
    const nextStatus = next.status ?? status
    const nextCompanyId = next.companyId ?? companyId
    if (nextStatus && nextStatus !== ALL) {
      params.set("status", nextStatus)
    } else {
      params.delete("status")
    }
    if (nextCompanyId && nextCompanyId !== ALL) {
      params.set("company_id", nextCompanyId)
    } else {
      params.delete("company_id")
    }
    const query = params.toString()
    router.replace(query ? `/jobs?${query}` : "/jobs")
  }

  return (
    <div className="flex flex-wrap items-end gap-4">
      <Field>
        <FieldLabel>状态</FieldLabel>
        <Select
          onValueChange={(value) => applyFilter({ status: typeof value === "string" ? value : "" })}
          value={status || ALL}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="全部状态">
              {(value) => {
                if (value === null || value === ALL) {
                  return "全部状态"
                }
                return statusOptions.find((option) => option.value === value)?.label ?? "全部状态"
              }}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>全部状态</SelectItem>
            {statusOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      {companies.length > 0 ? (
        <Field>
          <FieldLabel>企业</FieldLabel>
          <Select
            onValueChange={(value) =>
              applyFilter({ companyId: typeof value === "string" ? value : "" })
            }
            value={companyId || ALL}
          >
            <SelectTrigger className="w-56">
              <SelectValue placeholder="全部企业">
                {(value) => {
                  if (value === null || value === ALL) {
                    return "全部企业"
                  }
                  return companies.find((company) => company.id === value)?.name ?? "全部企业"
                }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部企业</SelectItem>
              {companies.map((company) => (
                <SelectItem key={company.id} value={company.id}>
                  {company.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      ) : null}
    </div>
  )
}
