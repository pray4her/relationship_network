import { fireEvent, render, screen } from "@testing-library/react"
import { expect, test, vi } from "vitest"

import { MfaSetupWizard } from "../src/components/security/mfa-setup-wizard"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}))

const idleStart = async () => ({ formError: null, setup: null })
const idleEnable = async () => ({ fieldErrors: {}, formError: null, recoveryCodes: null })

test("starts with a single setup call-to-action", () => {
  render(<MfaSetupWizard enableAction={idleEnable} startAction={idleStart} />)

  expect(screen.getByRole("button", { name: "设置两步验证" })).toBeInTheDocument()
})

test("advances to the secret and verification step after setup starts", async () => {
  // Given the start action returns the TOTP secret material
  const startAction = vi.fn(async () => ({
    formError: null,
    setup: { otpauthUrl: "otpauth://totp/demo?secret=ABC123", secret: "ABC123" },
  }))
  render(<MfaSetupWizard enableAction={idleEnable} startAction={startAction} />)

  // When the user begins the setup
  fireEvent.click(screen.getByRole("button", { name: "设置两步验证" }))

  // Then the manual-entry secret and the code input appear
  expect(await screen.findByText("ABC123")).toBeInTheDocument()
  expect(screen.getByLabelText("验证码")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "启用两步验证" })).toBeInTheDocument()
})

test("shows the recovery codes with the save warning after enabling", async () => {
  const recoveryCodes = Array.from({ length: 10 }, (_, index) => `rc-${index}`)
  const startAction = vi.fn(async () => ({
    formError: null,
    setup: { otpauthUrl: "otpauth://totp/demo?secret=ABC123", secret: "ABC123" },
  }))
  const enableAction = vi.fn(async () => ({
    fieldErrors: {},
    formError: null,
    recoveryCodes,
  }))
  render(<MfaSetupWizard enableAction={enableAction} startAction={startAction} />)

  fireEvent.click(screen.getByRole("button", { name: "设置两步验证" }))
  fireEvent.click(await screen.findByRole("button", { name: "启用两步验证" }))

  expect(await screen.findByText(/仅显示一次/)).toBeInTheDocument()
  for (const code of recoveryCodes) {
    expect(screen.getByText(code)).toBeInTheDocument()
  }
  expect(screen.getByRole("button", { name: "我已保存" })).toBeInTheDocument()
})
