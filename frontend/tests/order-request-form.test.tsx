import { fireEvent, render, screen } from "@testing-library/react"
import { expect, test, vi } from "vitest"

import { OrderRequestForm } from "../src/components/billing/order-request-form"

test("shows field errors returned by the action", async () => {
  // Given the action rejects the submission with a field error
  const action = vi.fn(async () => ({
    fieldErrors: { amount: "金额必须大于 0", payment_reference: "请输入付款凭证号" },
    formError: null,
    submitted: false,
  }))
  render(<OrderRequestForm action={action} idempotencyKey="test-order-key" />)

  // When the form is submitted
  fireEvent.click(screen.getByRole("button", { name: "提交订单申请" }))

  // Then the field errors are shown inline
  expect(await screen.findByText("金额必须大于 0")).toBeInTheDocument()
  expect(screen.getByText("请输入付款凭证号")).toBeInTheDocument()
})

test("shows the form error returned by the action", async () => {
  const action = vi.fn(async () => ({
    fieldErrors: {},
    formError: "没有执行该操作的权限",
    submitted: false,
  }))
  render(<OrderRequestForm action={action} idempotencyKey="test-order-key" />)

  fireEvent.click(screen.getByRole("button", { name: "提交订单申请" }))

  expect(await screen.findByText("没有执行该操作的权限")).toBeInTheDocument()
})

test("shows the success notice once the order is submitted", async () => {
  const action = vi.fn(async () => ({
    fieldErrors: {},
    formError: null,
    submitted: true,
  }))
  render(<OrderRequestForm action={action} idempotencyKey="test-order-key" />)

  fireEvent.click(screen.getByRole("button", { name: "提交订单申请" }))

  expect(await screen.findByRole("status")).toHaveTextContent(/订单已提交/)
})

test("submits the standard plan code as a hidden field", () => {
  const action = vi.fn()
  const { container } = render(<OrderRequestForm action={action} idempotencyKey="test-order-key" />)

  const planInput = container.querySelector<HTMLInputElement>("input[name='plan_code']")
  expect(planInput?.value).toBe("standard")
  expect(screen.getByText("标准版（按月订阅）")).toBeInTheDocument()

  // The render-scoped idempotency key rides along so retries reuse one order
  const keyInput = container.querySelector<HTMLInputElement>("input[name='idempotency_key']")
  expect(keyInput?.value).toBe("test-order-key")
})
