import { fireEvent, render, screen } from "@testing-library/react"
import { expect, test, vi } from "vitest"

import { MfaVerifyForm } from "../src/components/mfa-verify-form"

test("renders the factor choice and the code input", () => {
  const idleAction = async () => ({ fieldErrors: {}, formError: null })
  render(<MfaVerifyForm action={idleAction} />)

  expect(screen.getByRole("radio", { name: "身份验证器验证码" })).toBeChecked()
  expect(screen.getByRole("radio", { name: "恢复码" })).toBeInTheDocument()
  expect(screen.getByLabelText("验证码或恢复码")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "验证并登录" })).toBeInTheDocument()
})

test("renders the error returned by the action", async () => {
  const action = vi.fn(async () => ({ fieldErrors: {}, formError: "验证码不正确" }))
  render(<MfaVerifyForm action={action} />)

  fireEvent.click(screen.getByRole("button", { name: "验证并登录" }))

  expect(await screen.findByText("验证码不正确")).toBeInTheDocument()
})
