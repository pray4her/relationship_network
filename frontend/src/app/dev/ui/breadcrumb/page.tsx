import { Building2Icon, HomeIcon } from "lucide-react"

import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

import { PreviewPage, PreviewSection } from "../_preview"

export default function BreadcrumbPreviewPage() {
  return (
    <PreviewPage
      description="祖先保持真实链接，当前页是带 aria-current 的非链接文本；折叠项由 DropdownMenu 组合。"
      title="Breadcrumb"
    >
      <PreviewSection title="路径长度">
        <div className="grid gap-[var(--space-6)]">
          <Breadcrumb aria-label="企业详情路径">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink href="#breadcrumb-short">
                  <HomeIcon aria-hidden="true" />
                  首页
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink href="#breadcrumb-short">企业</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>示例企业</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>

          <Breadcrumb aria-label="折叠的职位材料路径">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink href="#breadcrumb-long">首页</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem className="relative">
                <BreadcrumbEllipsis aria-expanded="false" />
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink href="#breadcrumb-long">
                  <Building2Icon aria-hidden="true" />
                  职位
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>高级研究员</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
      </PreviewSection>

      <PreviewSection title="状态镜像">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink data-state="hover" href="#states">
                悬停
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink data-state="focus-visible" href="#states">
                焦点
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>当前页</BreadcrumbPage>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbEllipsis aria-expanded="true" />
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </PreviewSection>
    </PreviewPage>
  )
}
