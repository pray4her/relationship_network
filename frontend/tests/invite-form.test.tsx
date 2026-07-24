import { fireEvent, render, screen } from "@testing-library/react"
import { expect, test, vi } from "vitest"

import { InviteForm } from "../src/components/members/invite-form"

test("shows the invite link and token once after a successful invite", async () => {
  // Given the action creates an invitation and returns the one-time link
  const action = vi.fn(async () => ({
    createdInvitation: { inviteUrl: "http://localhost:3000/invite/tok-1", token: "tok-1" },
    fieldErrors: {},
    formError: null,
  }))
  render(<InviteForm action={action} />)

  // When the invite form is submitted
  fireEvent.click(screen.getByRole("button", { name: "邀请" }))

  // Then the link and token are displayed for manual delivery
  expect(await screen.findByText("http://localhost:3000/invite/tok-1")).toBeInTheDocument()
  expect(await screen.findByText("tok-1")).toBeInTheDocument()
  expect(screen.getByText(/仅显示一次/)).toBeInTheDocument()
})

test("shows the mapped error message when the invite fails", async () => {
  const action = vi.fn(async () => ({
    createdInvitation: null,
    fieldErrors: {},
    formError: "该邮箱已是租户成员",
  }))
  render(<InviteForm action={action} />)

  fireEvent.click(screen.getByRole("button", { name: "邀请" }))

  expect(await screen.findByText("该邮箱已是租户成员")).toBeInTheDocument()
})
