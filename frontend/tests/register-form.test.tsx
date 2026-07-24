import { fireEvent, render, screen } from "@testing-library/react"
import { expect, test, vi } from "vitest"

import { RegisterForm } from "../src/components/register-form"

const idleAction = async () => ({ fieldErrors: {}, formError: null })

test("renders every registration field with Chinese labels", () => {
  render(<RegisterForm action={idleAction} />)

  expect(screen.getByLabelText("邮箱")).toBeInTheDocument()
  expect(screen.getByLabelText("密码")).toBeInTheDocument()
  expect(screen.getByLabelText("显示名称")).toBeInTheDocument()
  expect(screen.getByLabelText("租户名称")).toBeInTheDocument()
  expect(screen.getByText("选填，留空则自动生成")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "创建账户" })).toBeInTheDocument()
})

test("renders validation messages returned by the action", async () => {
  // Given the action rejects the submission with field-level errors
  const action = vi.fn(async () => ({
    fieldErrors: { email: "邮箱格式不正确", password: "密码至少 8 位" },
    formError: null,
  }))
  render(<RegisterForm action={action} />)

  // When the form is submitted
  fireEvent.click(screen.getByRole("button", { name: "创建账户" }))

  // Then each invalid field shows its Chinese validation message
  expect(await screen.findByText("邮箱格式不正确")).toBeInTheDocument()
  expect(await screen.findByText("密码至少 8 位")).toBeInTheDocument()
  expect(action).toHaveBeenCalledOnce()
})

test("renders a form-level error returned by the action", async () => {
  // Given the action reports the email is already registered
  const action = vi.fn(async () => ({
    fieldErrors: { email: "该邮箱已注册，请直接登录" },
    formError: null,
  }))
  render(<RegisterForm action={action} />)

  // When the form is submitted
  fireEvent.click(screen.getByRole("button", { name: "创建账户" }))

  // Then the duplicate-email guidance is visible
  expect(await screen.findByText("该邮箱已注册，请直接登录")).toBeInTheDocument()
})
