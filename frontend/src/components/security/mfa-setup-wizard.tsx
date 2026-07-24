"use client"

import { useRouter } from "next/navigation"
import { QRCodeSVG } from "qrcode.react"
import { useActionState } from "react"

import type { MfaEnableFormState, MfaSetupStartState } from "@/app/actions/mfa"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"

type MfaSetupWizardProps = {
  readonly startAction: (
    state: MfaSetupStartState,
    formData: FormData,
  ) => Promise<MfaSetupStartState>
  readonly enableAction: (
    state: MfaEnableFormState,
    formData: FormData,
  ) => Promise<MfaEnableFormState>
}

export function MfaSetupWizard({ enableAction, startAction }: MfaSetupWizardProps) {
  const router = useRouter()
  const [startState, startFormAction, startPending] = useActionState(startAction, {
    formError: null,
    setup: null,
  })
  const [enableState, enableFormAction, enablePending] = useActionState(enableAction, {
    fieldErrors: {},
    formError: null,
    recoveryCodes: null,
  })

  if (enableState.recoveryCodes) {
    return (
      <div className="mfa-step">
        <p className="notice" role="alert">
          请立即保存以下恢复码，它们仅显示一次。丢失后将无法在无法使用身份验证器时登录。
        </p>
        <ol className="recovery-codes">
          {enableState.recoveryCodes.map((code) => (
            <li className="mono-value" key={code}>
              {code}
            </li>
          ))}
        </ol>
        <Button type="button" onClick={() => router.refresh()}>
          我已保存
        </Button>
      </div>
    )
  }

  if (startState.setup) {
    return (
      <div className="mfa-step">
        <p className="field-hint">
          第一步：使用身份验证器（如 Microsoft Authenticator、Google
          Authenticator）扫描下方二维码，或手动输入密钥。
        </p>
        <div className="qr-wrap">
          <QRCodeSVG size={180} value={startState.setup.otpauthUrl} />
        </div>
        <p>
          手动输入密钥：<span className="mono-value">{startState.setup.secret}</span>
        </p>
        <form action={enableFormAction} className="auth-form" noValidate>
          {enableState.formError ? (
            <p className="form-error" role="alert">
              {enableState.formError}
            </p>
          ) : null}
          <FormField
            autoComplete="one-time-code"
            error={enableState.fieldErrors.code}
            hint="第二步：输入身份验证器显示的 6 位验证码完成启用"
            id="code"
            label="验证码"
            type="text"
          />
          <Button type="submit" disabled={enablePending}>
            {enablePending ? "启用中…" : "启用两步验证"}
          </Button>
        </form>
      </div>
    )
  }

  return (
    <form action={startFormAction} className="auth-form" noValidate>
      {startState.formError ? (
        <p className="form-error" role="alert">
          {startState.formError}
        </p>
      ) : null}
      <p className="field-hint">启用后，登录时除密码外还需输入身份验证器验证码。</p>
      <Button type="submit" disabled={startPending}>
        {startPending ? "生成中…" : "设置两步验证"}
      </Button>
    </form>
  )
}
