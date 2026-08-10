import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
  AuthPanel,
  AuthPanelContent,
  AuthPanelDescription,
  AuthPanelHeader,
  AuthPanelTitle,
  DataRegion,
  DataRegionContent,
  DescriptionDetails,
  DescriptionItem,
  DescriptionList,
  DescriptionTerm,
  FormSection,
  FormSectionContent,
  FormSectionDescription,
  FormSectionHeader,
  FormSectionTitle,
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
  PageToolbar,
} from "@/components/layout/page"

describe("page layout primitives", () => {
  it("preserves the page landmark and heading hierarchy", () => {
    render(
      <Page>
        <PageHeader>
          <PageHeaderContent>
            <PageTitle>企业管理</PageTitle>
            <PageDescription>维护租户可用的企业档案。</PageDescription>
          </PageHeaderContent>
          <PageActions>
            <button type="button">新建企业</button>
          </PageActions>
        </PageHeader>
        <PageSection aria-labelledby="companies-heading">
          <PageSectionHeader>
            <PageSectionHeaderContent>
              <PageSectionTitle id="companies-heading">企业列表</PageSectionTitle>
            </PageSectionHeaderContent>
          </PageSectionHeader>
        </PageSection>
      </Page>,
    )

    expect(screen.getByRole("main")).toHaveAttribute("data-slot", "page")
    expect(screen.getByRole("heading", { level: 1, name: "企业管理" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { level: 2, name: "企业列表" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "新建企业" })).toBeInTheDocument()
  })

  it("allows the toolbar to render as the page-owned form", () => {
    render(
      <PageToolbar aria-label="筛选企业" render={<form action="/companies" method="get" />}>
        <label htmlFor="query">名称</label>
        <input id="query" name="query" />
      </PageToolbar>,
    )

    const toolbar = screen.getByRole("form", { name: "筛选企业" })
    expect(toolbar).toHaveAttribute("data-slot", "page-toolbar")
    expect(screen.getByLabelText("名称")).toHaveAttribute("name", "query")
  })

  it("keeps data, description, and form regions semantic", () => {
    render(
      <>
        <DataRegion aria-label="企业数据">
          <DataRegionContent>列表内容</DataRegionContent>
        </DataRegion>
        <DescriptionList aria-label="企业资料">
          <DescriptionItem>
            <DescriptionTerm>状态</DescriptionTerm>
            <DescriptionDetails>活跃</DescriptionDetails>
          </DescriptionItem>
        </DescriptionList>
        <FormSection aria-labelledby="profile-heading">
          <FormSectionHeader>
            <FormSectionTitle id="profile-heading">基本资料</FormSectionTitle>
            <FormSectionDescription>更新企业名称与说明。</FormSectionDescription>
          </FormSectionHeader>
          <FormSectionContent>
            <label htmlFor="name">企业名称</label>
            <input id="name" />
          </FormSectionContent>
        </FormSection>
      </>,
    )

    expect(screen.getByLabelText("企业数据")).toHaveAttribute("data-slot", "data-region")
    expect(screen.getByRole("term")).toHaveTextContent("状态")
    expect(screen.getByRole("definition")).toHaveTextContent("活跃")
    expect(screen.getByRole("region", { name: "基本资料" })).toHaveAttribute(
      "data-slot",
      "form-section",
    )
  })

  it("provides a standalone authentication panel without owning form behavior", () => {
    render(
      <AuthPanel aria-labelledby="login-heading">
        <AuthPanelHeader>
          <AuthPanelTitle id="login-heading">登录</AuthPanelTitle>
          <AuthPanelDescription>使用成员账户继续。</AuthPanelDescription>
        </AuthPanelHeader>
        <AuthPanelContent>
          <form>
            <button type="submit">登录</button>
          </form>
        </AuthPanelContent>
      </AuthPanel>,
    )

    expect(screen.getByRole("region", { name: "登录" })).toHaveAttribute("data-slot", "auth-panel")
    expect(screen.getByRole("button", { name: "登录" })).toHaveAttribute("type", "submit")
  })
})
