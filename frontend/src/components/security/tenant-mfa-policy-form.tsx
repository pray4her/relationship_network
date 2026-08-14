"use client"

import { useActionState, useEffect, useRef } from "react"
import { toast } from "sonner"

import type { TenantMfaPolicyFormState } from "@/app/actions/mfa"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

type TenantMfaPolicyFormProps = {
  readonly action: (
    state: TenantMfaPolicyFormState,
    formData: FormData,
  ) => Promise<TenantMfaPolicyFormState>
}

export function TenantMfaPolicyForm({ action }: TenantMfaPolicyFormProps) {
  const [state, formAction, isPending] = useActionState(action, {
    formError: null,
    notice: null,
    required: null,
  })
  const lastNotice = useRef(state.notice)

  useEffect(() => {
    if (state.notice !== null && state.notice !== lastNotice.current) {
      toast.success(state.notice)
    }
    lastNotice.current = state.notice
  }, [state.notice])

  // 当前策略没有可用的读取接口，首次加载时状态未知：此时保持按钮可用，
  // 提交一次后状态即变为已知，再禁用与当前状态一致的按钮，避免重复提交。
  const policyKnown = state.required !== null

  return (
    <div className="flex flex-col gap-4">
      {state.formError ? (
        <Alert variant="destructive">
          <AlertDescription>{state.formError}</AlertDescription>
        </Alert>
      ) : null}
      <p className="text-sm text-muted-foreground">
        开启后，所有未启用两步验证的成员将无法访问租户数据，直到完成 MFA 设置。
        {policyKnown
          ? state.required
            ? "当前状态：已开启。"
            : "当前状态：已关闭。"
          : "当前策略状态未知，请刷新后重试。"}
      </p>
      <div className="flex flex-wrap gap-2">
        <form action={formAction}>
          <input name="required" type="hidden" value="true" />
          <Button
            disabled={policyKnown && state.required === true}
            pending={isPending}
            type="submit"
          >
            开启强制 MFA
          </Button>
        </form>
        <form action={formAction}>
          <input name="required" type="hidden" value="false" />
          <Button
            disabled={policyKnown && state.required === false}
            pending={isPending}
            type="submit"
            variant="secondary"
          >
            关闭强制 MFA
          </Button>
        </form>
      </div>
    </div>
  )
}
