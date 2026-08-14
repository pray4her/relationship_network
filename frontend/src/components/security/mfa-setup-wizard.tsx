"use client"

import { useRouter } from "next/navigation"
import { QRCodeSVG } from "qrcode.react"
import { useActionState } from "react"

import type { MfaEnableFormState, MfaSetupStartState } from "@/app/actions/mfa"
import { FormField } from "@/components/form-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
      <div className="flex flex-col gap-4">
        <Alert variant="destructive">
          <AlertDescription>
            请立即保存以下恢复码，它们仅显示一次。丢失后将无法在无法使用身份验证器时登录。
          </AlertDescription>
        </Alert>
        <ol className="grid max-w-md grid-cols-2 gap-2">
          {enableState.recoveryCodes.map((code) => (
            <li
              className="rounded-md border bg-muted px-2.5 py-1.5 text-center font-mono text-sm break-all"
              key={code}
            >
              {code}
            </li>
          ))}
        </ol>
        <div>
          <Button type="button" onClick={() => router.refresh()}>
            我已保存
          </Button>
        </div>
      </div>
    )
  }

  if (startState.setup) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          第一步：使用身份验证器（如 Microsoft Authenticator、Google
          Authenticator）扫描下方二维码，或手动输入密钥。
        </p>
        {/* 二维码底必须保持纯白以保证扫码对比度，属语义 token 之外的刻意例外 */}
        <div className="w-fit rounded-lg border bg-white p-3">
          <QRCodeSVG size={180} value={startState.setup.otpauthUrl} />
        </div>
        <p>
          手动输入密钥：
          <span className="rounded-md border bg-muted px-2.5 py-1.5 font-mono text-sm break-all">
            {startState.setup.secret}
          </span>
        </p>
        <form action={enableFormAction} className="flex flex-col gap-4" noValidate>
          {enableState.formError ? (
            <Alert variant="destructive">
              <AlertDescription>{enableState.formError}</AlertDescription>
            </Alert>
          ) : null}
          <FormField
            autoComplete="one-time-code"
            error={enableState.fieldErrors.code}
            hint="第二步：输入身份验证器显示的 6 位验证码完成启用"
            id="code"
            inputMode="numeric"
            label="验证码"
            maxLength={6}
            type="text"
          />
          <div>
            <Button pending={enablePending} type="submit">
              启用两步验证
            </Button>
          </div>
        </form>
      </div>
    )
  }

  return (
    <form action={startFormAction} className="flex flex-col gap-4" noValidate>
      {startState.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{startState.formError}</AlertDescription>
        </Alert>
      ) : null}
      <p className="text-sm text-muted-foreground">
        启用后，登录时除密码外还需输入身份验证器验证码。
      </p>
      <div>
        <Button pending={startPending} type="submit">
          设置两步验证
        </Button>
      </div>
    </form>
  )
}
